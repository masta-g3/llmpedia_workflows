import sys, os
import pandas as pd
import re
from dotenv import load_dotenv

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import utils.vector_store as vs
import utils.app_utils as au
import utils.db.db_utils as db_utils
import utils.db.paper_db as paper_db
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "e3_extract_interesting_facts.log")


def parse_interesting_facts(xml_content):
    """Parse the XML-formatted interesting facts response."""
    facts = []

    # Extract content between <interesting_facts> tags
    match = re.search(
        r"<interesting_facts>(.*?)</interesting_facts>", xml_content, re.DOTALL
    )
    if not match:
        return facts

    xml_content = match.group(1)

    # Extract individual facts
    for i in range(1, 6):  # Up to 5 facts
        fact_match = re.search(
            rf"<interesting_fact{i}>(.*?)</interesting_fact{i}>", xml_content, re.DOTALL
        )
        if fact_match:
            # Clean up any extra whitespace
            fact = fact_match.group(1).strip()
            if fact:
                facts.append(fact)

    return facts


def main():
    logger.info("Starting interesting facts extraction process")
    vs.validate_openai_env()

    arxiv_codes = db_utils.get_arxiv_id_list("summary_notes")
    title_map = db_utils.get_arxiv_title_dict()

    # Get already processed codes by checking for papers with fact_id=1
    query = (
        "SELECT DISTINCT arxiv_code FROM summary_interesting_facts WHERE fact_id = 1"
    )
    existing_df = db_utils.execute_read_query(query)
    done_codes = existing_df["arxiv_code"].tolist() if not existing_df.empty else []

    arxiv_codes = list(set(arxiv_codes) - set(done_codes))
    arxiv_codes = sorted(arxiv_codes)[::-1]

    logger.info(f"Found {len(arxiv_codes)} papers to process for interesting facts")

    for arxiv_code in arxiv_codes:
        paper_title = title_map[arxiv_code]

        # Get paper markdown content from S3
        paper_content, success = au.get_paper_markdown(arxiv_code)

        if not success:
            logger.warning(
                f"Could not retrieve markdown content for {arxiv_code} - '{paper_title}', skipping..."
            )
            continue

        logger.info(
            f"Extracting interesting facts from: {arxiv_code} - '{paper_title}'"
        )
        interesting_facts_xml = vs.generate_paper_interesting_facts(
            paper_title, paper_content, model="claude-3-7-sonnet-20250219"
        )

        # Parse individual facts from XML response
        facts = parse_interesting_facts(interesting_facts_xml)

        if not facts:
            logger.warning(
                f"No valid facts found for {arxiv_code} - '{paper_title}', skipping..."
            )
            continue

        # Create a dataframe with each fact and its id
        data = []
        for fact_id, fact in enumerate(facts, 1):
            data.append(
                {
                    "arxiv_code": arxiv_code,
                    "fact_id": fact_id,
                    "fact": fact,
                    "tstp": pd.Timestamp.now(),
                }
            )

        df = pd.DataFrame(data)
        db_utils.upload_dataframe(df, "summary_interesting_facts")
        logger.info(f"Saved {len(facts)} interesting facts for {arxiv_code}")

    logger.info("Interesting facts extraction process completed")


if __name__ == "__main__":
    main()
