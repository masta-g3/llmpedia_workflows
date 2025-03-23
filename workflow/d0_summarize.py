import sys, os
import pandas as pd
from dotenv import load_dotenv

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import utils.vector_store as vs
import utils.paper_utils as pu
import utils.db.db_utils as db_utils
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "d0_summarize.log")

def shorten_list(list_str: str):
    """Shorten a bullet point list by taking the top 10 and bottom elements."""
    split_list = list_str.split("\n")
    if len(split_list) > 20:
        start_list_str = "\n".join(split_list[:5])
        end_list_str = "\n".join(split_list[-10:])
        list_str = f"{start_list_str}\n\n[...]\n{end_list_str}"
    return list_str

def main():
    """Summarize arxiv docs."""
    arxiv_codes = pu.list_s3_files("arxiv-text", strip_extension=True)
    done_codes = db_utils.get_arxiv_id_list("summary_notes")
    arxiv_codes = list(set(arxiv_codes) - set(done_codes))
    arxiv_codes = sorted(arxiv_codes)[::-1]
    
    total_papers = len(arxiv_codes)
    logger.info(f"Found {total_papers} papers to summarize.")

    for idx, arxiv_code in enumerate(arxiv_codes, 1):
        paper_content = pu.load_local(arxiv_code, "arxiv_text", format="txt", s3_bucket="arxiv-text")
        paper_content = pu.preprocess_arxiv_doc(paper_content)
        title_dict = db_utils.get_arxiv_title_dict()
        paper_title = title_dict.get(arxiv_code, None)
        if paper_title is None:
            logger.warning(f"[{idx}/{total_papers}] Could not find paper {arxiv_code} in the meta-database. Skipping.")
            continue

        logger.info(f"[{idx}/{total_papers}] Summarizing: {arxiv_code} - '{paper_title}'")
        summaries_dict, token_dict = vs.recursive_summarize_by_parts(
            paper_title,
            paper_content,
            max_tokens=500,
            model="gemini/gemini-2.0-flash",
            verbose=False,
        )

        summary_notes = pd.DataFrame(
            summaries_dict.items(), columns=["level", "summary"]
        )
        summary_notes["tokens"] = summary_notes.level.map(token_dict)
        summary_notes["arxiv_code"] = arxiv_code
        summary_notes["tstp"] = pd.Timestamp.now()
        
        db_utils.upload_dataframe(summary_notes, "summary_notes", if_exists="append")

    logger.info("Paper summarization process completed.")

if __name__ == "__main__":
    main()
