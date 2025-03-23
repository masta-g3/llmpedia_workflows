import sys, os
from datetime import datetime
from dotenv import load_dotenv

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

import utils.paper_utils as pu
import utils.db.db_utils as db_utils
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "z0_update_gist.log")

def main():
    logger.info("Starting gist update process")
    
    ## Check key is on env.
    if "GITHUB_TOKEN" not in os.environ:
        raise ValueError("Please set GITHUB_TOKEN in .env file.")

    ## Params.
    arxiv_codes = db_utils.get_arxiv_id_list("summaries")
    title_map = db_utils.get_arxiv_title_dict()
    title_map = {k: v for k, v in title_map.items() if k in arxiv_codes}
    titles = list(title_map.values())
    
    total_papers = len(titles)
    logger.info(f"Found {total_papers} papers to add to gist")

    token = os.environ["GITHUB_TOKEN"]
    gist_id = "8f7227397b1053b42e727bbd6abf1d2e"
    gist_filename = "llm_papers.txt"
    gist_description = f"Updated {datetime.now().strftime('%Y-%m-%d')}"
    gist_content = "\n".join(titles)

    ## Write to disk.
    gist_path = os.path.join(PROJECT_PATH, "data", gist_filename)
    with open(gist_path, "w") as f:
        f.write(gist_content)
    logger.info(f"Saved {total_papers} paper titles to {gist_filename}")

    ## Execute.
    gist_url = pu.update_gist(token, gist_id, gist_filename, gist_description, gist_content)
    logger.info(f"Updated gist with {total_papers} papers: {gist_url}")


if __name__ == "__main__":
    main()