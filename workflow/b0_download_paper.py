import sys, os
from dotenv import load_dotenv

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import re
import time

import utils.paper_utils as pu
import utils.vector_store as vs
import utils.db.db_utils as db_utils
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "b0_download_paper.log")


def update_gist(gist_id, gist_filename, paper_list, logger):
    """Update the gist with the current queue."""
    gist_url = pu.update_gist(
        os.environ["GITHUB_TOKEN"],
        gist_id,
        gist_filename,
        "Updated LLM queue.",
        "\n".join(paper_list),
    )
    return gist_url


def main():
    logger.info("Starting paper download process.")
    vs.validate_openai_env()
    parsed_list = []

    ## Get paper list.
    gist_id = "1dd189493c1890df6e04aaea6d049643"
    gist_filename = "llm_queue.txt"
    paper_list = pu.fetch_queue_gist(gist_id, gist_filename)
    x_paper_list = list(set(db_utils.get_arxiv_id_list(table_name="llm_tweets")))
    x_paper_list = [p for p in x_paper_list if pu.is_arxiv_code(p)]
    logger.info(f"Fetched {len(paper_list)} papers from gist.")

    ## Check local files.
    paper_list = list(set(paper_list + x_paper_list))
    done_codes = pu.list_s3_files("arxiv-text", strip_extension=True)
    nonllm_codes = pu.list_s3_files("nonllm-arxiv-text", strip_extension=True) + ["..."]
    logger.info(
        f"Found {len(done_codes)} done papers and {len(nonllm_codes)} non-LLM papers."
    )

    ## Remove duplicates.
    paper_list = list(set(paper_list) - set(done_codes) - set(nonllm_codes))
    paper_list_iter = sorted(paper_list[:])[::-1]
    total_papers = len(paper_list_iter)
    logger.info(f"{total_papers} papers to process after removing duplicates.")

    arxiv_map = db_utils.get_arxiv_title_dict()
    existing_paper_names = list(arxiv_map.values())
    existing_paper_ids = list(arxiv_map.keys())

    ## Iterate.
    gist_url = None
    for idx, paper_name in enumerate(paper_list_iter, 1):
        time.sleep(3)
        existing = pu.check_if_exists(
            paper_name, existing_paper_names, existing_paper_ids
        )

        ## Check if we already have the document.
        if existing:
            logger.info(
                f"[{idx}/{total_papers}] Skipping: '{paper_name}' (already in database)"
            )
            ## Update gist.
            parsed_list.append(paper_name)
            paper_list = list(set(paper_list) - set(parsed_list))
            gist_url = update_gist(gist_id, gist_filename, paper_list, logger)
            continue

        ## Search content.
        try:
            new_doc = pu.search_arxiv_doc(paper_name)
        except Exception as e:
            logger.error(
                f"[{idx}/{total_papers}] Failed to search: '{paper_name}' - {str(e)}"
            )
            continue

        if new_doc is None:
            logger.warning(
                f"[{idx}/{total_papers}] Not found in ArXiv: '{paper_name}'"
            )
            continue

        new_meta = new_doc.metadata
        new_content = pu.preprocess_arxiv_doc(new_doc.page_content)
        title = new_meta["Title"]
        arxiv_code = new_meta["entry_id"].split("/")[-1]
        arxiv_code = re.sub(r"v\d+$", "", arxiv_code)

        ## Verify it's an LLM paper.
        is_llm_paper = vs.verify_llm_paper(
            new_content[:1500] + " ...[continued]...",
            model="claude-3-5-sonnet-20241022",
        )
        if not is_llm_paper["is_related"]:
            logger.info(
                f"[{idx}/{total_papers}] Not LLM paper: {arxiv_code} - '{title}'"
            )
            parsed_list.append(paper_name)
            paper_list = list(set(paper_list) - set(parsed_list))
            gist_url = update_gist(gist_id, gist_filename, paper_list, logger)
            ## Store in nonllm_arxiv_text.
            pu.store_local(new_content, arxiv_code, "nonllm_arxiv_text", format="txt")
            pu.upload_s3_file(
                arxiv_code, "nonllm-arxiv-text", prefix="data", format="txt"
            )
            continue

        ## Check if we have a summary locally.
        local_paper_codes = os.path.join(
            os.environ.get("PROJECT_PATH"), "data", "arxiv_text"
        )
        local_paper_codes = [f.split(".json")[0] for f in os.listdir(local_paper_codes)]
        if arxiv_code in local_paper_codes:
            ## Update gist.
            logger.info(
                f"[{idx}/{total_papers}] Found locally: {arxiv_code} - '{title}'"
            )
            parsed_list.append(paper_name)
            paper_list = list(set(paper_list) - set(parsed_list))
            gist_url = update_gist(gist_id, gist_filename, paper_list, logger)
            continue

        ## Store.
        pu.store_local(new_content, arxiv_code, "arxiv_text", format="txt")
        pu.upload_s3_file(arxiv_code, "arxiv-text", prefix="data", format="txt")
        logger.info(
            f"[{idx}/{total_papers}] Stored paper: {arxiv_code} - '{title}'"
        )

        ## Update gist.
        parsed_list.append(paper_name)
        paper_list = list(set(paper_list) - set(parsed_list))
        gist_url = update_gist(gist_id, gist_filename, paper_list, logger)

    if gist_url:
        logger.info(f"Done! Updated queue gist URL: {gist_url}")


if __name__ == "__main__":
    main()
