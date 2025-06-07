import sys, os
import pandas as pd
from dotenv import load_dotenv

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import utils.vector_store as vs
import utils.paper_utils as pu
import utils.app_utils as au
import utils.db.db_utils as db_utils
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "d1_summarize_new.log")


def main():
    """Summarize arxiv docs using full markdown content."""

    # Get the list of arxiv codes from S3 directories.
    arxiv_codes = pu.list_s3_directories("arxiv-md")
    done_codes = db_utils.get_arxiv_id_list("summary_notes")
    arxiv_codes = list(set(arxiv_codes) - set(done_codes))
    arxiv_codes = sorted(arxiv_codes)[::-1]

    total_papers = len(arxiv_codes)
    logger.info(f"Found {total_papers} papers to summarize.")

    ## Define the paragraph lengths to use.
    paragraph_lengths = [1, 2, 3, 5, 10, 20]

    for idx, arxiv_code in enumerate(arxiv_codes, 1):
        ## Get paper markdown content.
        paper_content, success = au.get_paper_markdown(arxiv_code)
        ## Limit content to ~150000 tokens (1 token = 4 characters).
        paper_content = paper_content[:100000 * 4]

        if not success:
            logger.warning(
                f"[{idx}/{total_papers}] Could not fetch markdown for paper {arxiv_code}. Skipping."
            )
            continue

        title_dict = db_utils.get_arxiv_title_dict()
        paper_title = title_dict.get(arxiv_code, None)
        if paper_title is None:
            logger.warning(
                f"[{idx}/{total_papers}] Could not find paper {arxiv_code} in the meta-database. Skipping."
            )
            continue

        logger.info(
            f"[{idx}/{total_papers}] Summarizing: {arxiv_code} - '{paper_title}'"
        )

        ## Create a DataFrame to store the summaries.
        summary_notes_list = []
        summary = "N/A"

        ## Generate summaries for each paragraph length.
        for paragraphs in paragraph_lengths:
            # logger.info(f"  Generating {paragraphs}-paragraph summary...")
            previous_notes = summary[:]

            summary = vs.summarize_full_document(
                paper_title,
                paper_content,
                paragraphs=paragraphs,
                previous_notes=previous_notes,
                model="claude-3-7-sonnet-20250219",
            )

            ## Create a row for this summary.
            tokens = len(vs.token_encoder.encode(summary))
            summary_notes_list.append(
                {
                    "level": paragraphs,
                    "summary": summary,
                    "tokens": tokens,
                    "arxiv_code": arxiv_code,
                    "tstp": pd.Timestamp.now(),
                    "method": "full_text",
                }
            )

            # logger.info(
            #     f"  Completed {paragraphs}-paragraph summary ({tokens} tokens)."
            # )

        ## Convert list to DataFrame and upload.
        summary_notes = pd.DataFrame(summary_notes_list)
        db_utils.upload_dataframe(summary_notes, "summary_notes", if_exists="append")

        # logger.info(f"Completed summarization for {arxiv_code}")

    logger.info("Paper summarization process completed.")


if __name__ == "__main__":
    main()
