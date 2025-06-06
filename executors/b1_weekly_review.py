import sys, os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import utils.paper_utils as pu
import utils.vector_store as vs
import utils.db.paper_db as paper_db
import utils.db.db_utils as db_utils
import utils.db.tweet_db as tweet_db
from utils.logging_utils import setup_logger

# Set up logging
logger = setup_logger(__name__, "weekly_review.log")

## Constants
DEFAULT_MODEL = "claude-3-7-sonnet-20250219"

## AUXILIARY FUNCTIONS ##

def prepare_date(date_str: str) -> tuple[str, pd.Timestamp]:
    """Converts date_str to datetime and shifts to previous Monday if needed."""
    date_str_dt = pd.to_datetime(date_str)
    days_since_monday = date_str_dt.weekday()
    if days_since_monday > 0:
        date_str_dt = date_str_dt - pd.Timedelta(days=days_since_monday)
        date_str = date_str_dt.strftime("%Y-%m-%d")
    logger.info(f"Processing weekly review for week of {date_str}")
    return date_str, date_str_dt

def get_weekly_data(current_date_str: str, date_st_dt: pd.Timestamp) -> tuple[pd.DataFrame, dict, list[str]]:
    """Fetches weekly content dataframe and past weekly counts."""
    weekly_content_df = paper_db.get_weekly_summary_inputs(current_date_str)
    logger.info(f"Found {len(weekly_content_df)} papers for the week {current_date_str}")

    ## Get weekly total counts for the last 16 weeks.
    prev_mondays_dt_range = pd.date_range(
        date_st_dt - pd.Timedelta(days=7 * 16), date_st_dt, freq="W-MON"
    )
    prev_mondays_str_list = [date.strftime("%Y-%m-%d") for date in prev_mondays_dt_range]
    weekly_counts = {
        d_str: len(paper_db.get_weekly_summary_inputs(d_str))
        for d_str in prev_mondays_str_list
    }
    logger.info("Retrieved weekly counts for the past 16 weeks")
    return weekly_content_df, weekly_counts, prev_mondays_str_list

def get_previous_themes_str(prev_mondays_str_list: list[str]) -> str:
    """Retrieves themes from previous weeks' summaries."""
    try:
        previous_summaries = []
        for i in range(2, 6): 
            if len(prev_mondays_str_list) > i:
                summary = paper_db.get_weekly_content(
                    prev_mondays_str_list[-i], content_type="content"
                )
                if summary:
                    previous_summaries.append(summary)
        
        if previous_summaries:
            previous_themes = "\n".join([s.split("\n")[0] for s in previous_summaries if s])
            logger.info(f"Retrieved {len(previous_summaries)} previous weeks' themes")
        else:
            previous_themes = "N/A"
            logger.info("No previous themes found or previous summaries were empty.")

    except Exception as e:
        logger.warning(f"Could not retrieve previous themes due to: {e}. Falling back to old method.")
        if len(prev_mondays_str_list) > 1:
            previous_summary_old = paper_db.get_weekly_summary_old(prev_mondays_str_list[-2])
            if previous_summary_old is None:
                previous_themes = "N/A"
                logger.warning("Could not find previous week's summary using old method either.")
            else:
                split_summary = previous_summary_old.split("\n##")
                if len(split_summary) > 2:
                    previous_themes = split_summary[2]
                else:
                    previous_themes = previous_summary_old
                logger.info("Retrieved previous week's summary themes from old format")
        else:
            previous_themes = "N/A"
            logger.warning("Not enough past Mondays to fetch previous themes.")
            
    return previous_themes

def format_weekly_content_markdown(
    date_st_dt: pd.Timestamp,
    current_date_str: str,
    weekly_content_df: pd.DataFrame,
    weekly_counts: dict,
) -> tuple[str, list[str]]:
    """Formats the main markdown content for the weekly review."""
    date_end_dt = date_st_dt + pd.Timedelta(days=6)
    date_st_long_str = date_st_dt.strftime("%B %d, %Y")
    date_end_long_str = date_end_dt.strftime("%B %d, %Y")
    
    md_content = f"# Weekly Review ({date_st_long_str} to {date_end_long_str})\n\n"
    md_content += f"## Weekly Publication Trends\n"
    md_content += "| Week | Total Papers |\n"
    md_content += "| --- | --- |\n"
    
    sorted_weekly_counts = sorted(weekly_counts.items(), key=lambda item: pd.to_datetime(item[0]))

    for tmp_date_str, count in sorted_weekly_counts:
        iter_date_dt = pd.to_datetime(tmp_date_str)
        iter_date_st_long_str = iter_date_dt.strftime("%B %d, %Y")
        iter_date_end_dt = iter_date_dt + pd.Timedelta(days=6)
        iter_date_end_long_str = iter_date_end_dt.strftime("%B %d, %Y")
        if tmp_date_str == current_date_str:
            md_content += (
                f"| **{iter_date_st_long_str} to {iter_date_end_long_str}** | **{count}** |\n"
            )
        else:
            md_content += f"| {iter_date_st_long_str} to {iter_date_end_long_str} | {count} |\n"
    md_content += "\n\n"

    md_content += f"## Papers Published This Week\n"
    html_markdowns = []
    for _, row in weekly_content_df.iterrows():
        paper_markdown = pu.format_paper_summary(row)
        md_content += paper_markdown
        if "http" in paper_markdown:
            html_markdowns.append(paper_markdown)
            
    logger.info("Formatted weekly content markdown")
    return md_content, html_markdowns

def get_tweet_analysis_markdown(date_st_dt: pd.Timestamp) -> str:
    """Fetches and formats tweet analysis for the week."""
    logger.info("Fetching tweet analysis for the week")
    week_end_dt = date_st_dt + pd.Timedelta(days=6)
    tweet_analysis_df = tweet_db.get_tweet_analysis_between(date_st_dt, week_end_dt)

    if tweet_analysis_df.empty:
        tweet_analysis_md_str = "No tweet analysis available for this week."
        logger.info("No tweet analysis found for the week.")
    else:
        tweet_analysis_md_str = "## Community Discussions\n" + "\n\n".join(
            tweet_analysis_df["response"].tolist()
        )
        logger.info(f"Formatted {tweet_analysis_df.shape[0]} tweet analysis entries.")
    return tweet_analysis_md_str

def generate_report_and_highlight(
    weekly_content_markdown_str: str,
    tweet_analysis_markdown_str: str
) -> tuple[str, str]:
    """Generates weekly summary report and highlight using LLM."""
    logger.info("Generating weekly report using LLM")
    summary_obj_str = vs.generate_weekly_report(
        weekly_content_markdown_str, tweet_analysis_md=tweet_analysis_markdown_str, llm_model=DEFAULT_MODEL
    )
    summary_obj_str = (
        summary_obj_str.replace("<new_developments_findings>", "")
        .replace("</new_developments_findings>", "")
        .strip()
    )

    logger.info("Generating weekly highlight using LLM")
    highlight_str = vs.generate_weekly_highlight(
        weekly_content_markdown_str, llm_model=DEFAULT_MODEL
    )
    return summary_obj_str, highlight_str

def prepare_data_for_storage(
    current_date_str: str,
    weekly_summary_str: str,
    weekly_highlight_str: str
) -> pd.DataFrame:
    """Prepares the DataFrame for database storage."""
    logger.info("Formatting and preparing data for storage")
    report_date_dt = pd.to_datetime(current_date_str)
    timestamp_now = pd.Timestamp.now()

    data_df = pd.DataFrame(
        {
            "content": [weekly_summary_str],
            "highlight": [weekly_highlight_str],
            "scratchpad_papers": [None], 
            "scratchpad_themes": [None], 
            "date": [report_date_dt],
            "tstp": [timestamp_now],
        }
    )
    return data_df

def store_weekly_review_data(data_to_store: pd.DataFrame):
    """Uploads the weekly review data to the database."""
    logger.info("Uploading weekly content to database")
    db_utils.upload_dataframe(data_to_store, "weekly_content")
    logger.info(f"Successfully stored weekly review for date: {data_to_store['date'].iloc[0].strftime('%Y-%m-%d')}")

def main(date_str_input: str):
    """Generate a weekly review of highlights and takeaways from papers."""
    
    current_date_str, date_st_dt = prepare_date(date_str_input)

    vs.validate_openai_env()
    if paper_db.check_weekly_summary_exists(current_date_str):
        logger.info(f"Weekly summary for {current_date_str} already exists. Skipping...")
        return

    weekly_content_df, weekly_counts, prev_mondays_str_list = get_weekly_data(current_date_str, date_st_dt)
    
    previous_themes_text = get_previous_themes_str(prev_mondays_str_list)

    llm_input_markdown_main_content, _ = format_weekly_content_markdown(
        date_st_dt, current_date_str, weekly_content_df, weekly_counts
    )
    
    llm_input_markdown = llm_input_markdown_main_content
    llm_input_markdown += f"\n## Previous Week's Submissions for New Developments and Themes\nBelow is the introduction section from recent previous weeks. Pay close attention to the themes mentioned so you don't repeat them.\n"
    llm_input_markdown += f"```{previous_themes_text}```\n\n"

    tweet_analysis_markdown_text = get_tweet_analysis_markdown(date_st_dt)
    
    weekly_summary_text, weekly_highlight_text = generate_report_and_highlight(
        llm_input_markdown, tweet_analysis_markdown_text
    )
    
    data_for_db = prepare_data_for_storage(
        current_date_str, weekly_summary_text, weekly_highlight_text
    )
    
    store_weekly_review_data(data_for_db)
    
    logger.info(f"Successfully completed weekly review generation for {current_date_str}")

if __name__ == "__main__":
    run_date_str = sys.argv[1] if len(sys.argv) == 2 else "2025-05-19"
    main(run_date_str)
