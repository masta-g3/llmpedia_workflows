import sys, os
import pandas as pd
from dotenv import load_dotenv

# Project path setup
PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
sys.path.append(PROJECT_PATH)
os.chdir(PROJECT_PATH)  # Change current directory

# Imports from the project
import utils.vector_store as vs
import utils.paper_utils as pu
import utils.app_utils as au
import utils.db.db_utils as db_utils

# import utils.db.paper_db as paper_db # Not directly used in the refined combined logic
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "d2_summarize_full.log")

summarization_model = "claude-3-7-sonnet-20250219"
facts_model = "claude-3-7-sonnet-20250219"
context_size = 5000


def parse_interesting_facts(xml_content):
    """Parse the XML-formatted interesting facts response."""
    facts = []
    ## Assuming pu.extract_tagged_content exists and works as in e3_extract_interesting_facts.py
    outer_content = pu.extract_tagged_content(xml_content, ["interesting_facts"])
    if not outer_content.get("interesting_facts"):
        return facts

    fact_tags = [f"interesting_fact{i}" for i in range(1, 6)]
    facts_dict = pu.extract_tagged_content(
        outer_content["interesting_facts"], fact_tags
    )
    facts = [fact for fact in facts_dict.values() if fact]
    return facts


def summarize_paper(arxiv_code, paper_title, paper_content, model_name):
    """Generates summaries for a paper at multiple paragraph lengths and uploads them."""
    logger.info(f"Starting summarization for {arxiv_code} - '{paper_title}'")
    paragraph_lengths = [1, 3, 5, 10]  # [2, 20] are not used anymore
    summary_notes_list = []
    current_summary_text = "N/A"  ## Initial text for the first 'previous_notes'

    for paragraphs in paragraph_lengths:
        # logger.debug(f"  Generating {paragraphs}-paragraph summary for {arxiv_code}...")
        previous_notes_for_model = current_summary_text[:]

        generated_summary_text = vs.summarize_full_document(
            paper_title,
            paper_content,
            paragraphs=paragraphs,
            previous_notes=previous_notes_for_model,
            model=model_name,
        )
        current_summary_text = (
            generated_summary_text  ## Update for the next iteration's previous_notes
        )

        tokens = len(
            vs.token_encoder.encode(generated_summary_text)
        )  # Assuming vs.token_encoder is available
        summary_notes_list.append(
            {
                "level": paragraphs,
                "summary": generated_summary_text,
                "tokens": tokens,
                "arxiv_code": arxiv_code,
                "tstp": pd.Timestamp.now(),
                "method": "full_text",
            }
        )
        # logger.debug(f"  Completed {paragraphs}-paragraph summary for {arxiv_code} ({tokens} tokens).")

    if summary_notes_list:
        summary_notes_df = pd.DataFrame(summary_notes_list)
        db_utils.upload_dataframe(summary_notes_df, "summary_notes", if_exists="append")
        logger.info(f"Successfully stored summaries for {arxiv_code} - '{paper_title}'")
        return True
    else:
        logger.warning(f"No summaries generated for {arxiv_code} - '{paper_title}'")
        return False


def extract_facts_for_paper(arxiv_code, paper_title, paper_content, model_name):
    """Extracts interesting facts for a paper and uploads them."""
    logger.info(
        f"Starting interesting facts extraction for {arxiv_code} - '{paper_title}'"
    )

    interesting_facts_xml = vs.generate_paper_interesting_facts(
        paper_title, paper_content, model=model_name
    )
    facts = parse_interesting_facts(interesting_facts_xml)

    if not facts:
        raise ValueError(
            f"No valid facts found for {arxiv_code} - '{paper_title}'. Expected at least 1 fact."
        )

    data = []
    for fact_id, fact_text in enumerate(facts, 1):
        data.append(
            {
                "arxiv_code": arxiv_code,
                "fact_id": fact_id,
                "fact": fact_text,
                "tstp": pd.Timestamp.now(),
            }
        )
    if data:
        facts_df = pd.DataFrame(data)
        db_utils.upload_dataframe(facts_df, "summary_interesting_facts")
        logger.info(
            f"Successfully stored interesting facts for {arxiv_code} - '{paper_title}'"
        )
        return True
    return False


def main():
    logger.info(
        "Starting combined paper processing: Summarization and Interesting Facts Extraction."
    )
    vs.validate_openai_env()

    ## Get all papers that have markdown content
    all_md_papers = set(pu.list_s3_directories("arxiv-md"))
    if not all_md_papers:
        logger.info(
            "No papers with markdown content found in S3 'arxiv-md' directory. Exiting."
        )
        return

    ## Get lists of already processed papers to determine what needs to be done
    summarized_codes_db = set(db_utils.get_arxiv_id_list("summary_notes"))
    fact_extracted_codes_db = set(
        db_utils.get_arxiv_id_list("summary_interesting_facts")
    )
    title_map = db_utils.get_arxiv_title_dict()

    ## Determine papers that need summarization (primary task)
    papers_needing_summarization = sorted(
        list(all_md_papers - summarized_codes_db), reverse=True
    )

    total_papers_to_process = len(papers_needing_summarization)
    if total_papers_to_process == 0:
        logger.info("No new papers found requiring summarization. Exiting.")
        return

    logger.info(f"Found {total_papers_to_process} papers requiring summarization.")

    summaries_added_count = 0
    facts_added_count = 0

    for idx, arxiv_code in enumerate(papers_needing_summarization, 1):
        log_prefix = f"[{idx}/{total_papers_to_process}] {arxiv_code}:"
        logger.info(f"{log_prefix} Starting processing for summarization.")

        paper_title = title_map.get(arxiv_code)
        if not paper_title:
            logger.warning(
                f"{log_prefix} Could not find title in meta-database. Skipping."
            )
            continue

        paper_content, success = au.get_paper_markdown(arxiv_code)
        if not success:
            logger.warning(
                f"{log_prefix} Could not retrieve markdown for '{paper_title}'. Skipping."
            )
            continue
        paper_content = paper_content[: context_size * 4]  # Limit content size

        ## Task 1: Summarization (for papers in papers_needing_summarization)
        summary_succeeded_this_run = False
        if summarize_paper(arxiv_code, paper_title, paper_content, summarization_model):
            summaries_added_count += 1
            summary_succeeded_this_run = True
            # No need to add to summarized_codes_db here as we are iterating based on its absence
        else:
            logger.warning(f"{log_prefix} Summarization failed for '{paper_title}'.")
            # Continue to the next paper, as fact extraction depends on successful summarization
            continue

        ## Task 2: Interesting Facts Extraction (only if summarization succeeded in this run)
        if summary_succeeded_this_run and arxiv_code not in fact_extracted_codes_db:
            logger.info(
                f"{log_prefix} Attempting interesting facts extraction for '{paper_title}' (post-summarization)."
            )
            if extract_facts_for_paper(
                arxiv_code, paper_title, paper_content, facts_model
            ):
                facts_added_count += 1
                # fact_extracted_codes_db.add(arxiv_code) # Optionally update local set if needed for other logic (not strictly needed here)
            else:
                logger.warning(
                    f"{log_prefix} Interesting facts extraction failed for '{paper_title}'."
                )
        elif arxiv_code in fact_extracted_codes_db:
            logger.info(
                f"{log_prefix} Facts already exist for '{paper_title}'. Skipping fact extraction."
            )
        # No explicit 'else' for failed summary here, as we 'continue' in that case above.

        logger.info(f"{log_prefix} Finished processing '{paper_title}'.")

    logger.info(f"Combined paper processing completed.")
    logger.info(f"Total summaries generated in this run: {summaries_added_count}.")
    logger.info(
        f"Total sets of interesting facts generated in this run: {facts_added_count}."
    )


if __name__ == "__main__":
    main()
