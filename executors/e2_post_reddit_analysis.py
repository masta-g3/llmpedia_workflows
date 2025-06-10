#!/usr/bin/env python3

"""
Script to post the latest Reddit cross-analysis to X.com.
Reads the most recent cross-subreddit analysis from the database and posts it as a tweet
with a nostalgic news report style format.
"""

import os
import sys
import argparse
from typing import Optional
import pandas as pd
import pytz

from dotenv import load_dotenv

# Add project path to sys.path
PROJECT_PATH = os.getenv(
    "PROJECT_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

# Local imports
from utils.logging_utils import setup_logger
import utils.db.reddit_db as reddit_db
from utils.tweet import send_tweet2, TweetThread, boldify, bold
import utils.notifications as em

logger = setup_logger(__name__, "e2_post_reddit_analysis.log")

# Report title variations - aligned with d2_post_analysis.py but for Reddit
REPORT_EMOJIS = ["🌐", "📡", "🔍", "💬", "📊", "⚡", "🗨️"]
REPORT_TITLE = "LLMpedia Reddit Signal Report"
NEWS_TITLES = [f"{emoji} {REPORT_TITLE}" for emoji in REPORT_EMOJIS]


def get_latest_reddit_analysis() -> Optional[dict]:
    """Retrieve the latest unposted Reddit cross-analysis from the database with safeguards.
    
    Only processes cross-subreddit analyses (subreddit="multi").
    """
    logger.info("Fetching latest unposted Reddit cross-analysis")

    # Only get cross-subreddit analyses (subreddit="multi")
    unposted_df = reddit_db.get_unposted_reddit_analyses(
        max_age_hours=3, subreddit="multi"
    )

    if unposted_df.empty:
        logger.info("No unposted Reddit cross-analyses found within the last 3 hours")
        return None

    # Get the timestamp of the last analysis that was successfully posted
    last_posted_tstp_utc = reddit_db.get_last_posted_analysis_timestamp(
        subreddit="multi"
    )

    if last_posted_tstp_utc:
        # Ensure we only consider analyses created AFTER the last one posted
        last_posted_tstp_utc = pd.to_datetime(last_posted_tstp_utc, utc=True)
        unposted_df["tstp_utc"] = pd.to_datetime(unposted_df["tstp"], utc=True)

        unposted_df = unposted_df[unposted_df["tstp_utc"] > last_posted_tstp_utc]

        if unposted_df.empty:
            logger.info(
                f"No new unposted cross-analyses found after the last posted one (at {last_posted_tstp_utc.strftime('%Y-%m-%d %H:%M:%S %Z')})."
            )
            return None
        logger.info(
            f"Found {len(unposted_df)} new cross-analyses since last post at {last_posted_tstp_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

    # Get the oldest unposted analysis from the (potentially filtered) list for proper sequencing
    latest_analysis_series = unposted_df.iloc[0]

    # Convert to dict for easier handling
    analysis_data = {
        "id": int(latest_analysis_series["id"]),  # Convert numpy.int64 to Python int
        "timestamp": latest_analysis_series["tstp"],  # Analysis creation time
        "subreddit": latest_analysis_series["subreddit"],
        "unique_posts": latest_analysis_series["unique_posts"],
        "total_comments": latest_analysis_series["total_comments"],
        "response": latest_analysis_series["response"],
        "thinking_process": latest_analysis_series.get("thinking_process", ""),
    }

    # Get the creation time for logging purposes
    analysis_creation_time_utc = pd.to_datetime(analysis_data["timestamp"], utc=True)

    logger.info(
        f"Selected unposted cross-subreddit analysis ID {analysis_data['id']} created at {analysis_creation_time_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )

    return analysis_data


def format_reddit_analysis_tweet(analysis_data: dict, title: str) -> str:
    """Format the Reddit analysis data into a tweet with nostalgic news report style."""
    # analysis_data['timestamp'] is the UTC creation time of the analysis
    utc_timestamp = pd.to_datetime(analysis_data["timestamp"], utc=True)
    response = analysis_data["response"]

    # Convert UTC to PST for display in the tweet
    pst = pytz.timezone("US/Pacific")
    pst_timestamp = utc_timestamp.astimezone(pst)

    time_str = pst_timestamp.strftime("%H:%M %Z")  # e.g., 14:30 PST
    date_str = pst_timestamp.strftime("%b %d")  # e.g., May 23

    # Format title in bold and "Stay tuned" line in italics using custom functions
    bold_title = boldify(title)

    # Create the tweet content with formatting
    tweet_content = f"""{bold_title} - {date_str}, {time_str}

{response}

🔗 **Stay tuned for the next bulletin**"""

    # Apply the bold function to process the ** syntax for italics
    tweet_content = bold(tweet_content)

    return tweet_content


def post_reddit_analysis_tweet(analysis_data: dict, title: str) -> bool:
    """Post the Reddit cross-analysis as a tweet to X.com."""
    logger.info(f"Formatting tweet with title: {title}")
    tweet_content = format_reddit_analysis_tweet(analysis_data, title)

    logger.info(f"Tweet content length: {len(tweet_content)} characters")

    # Create a simple tweet thread
    thread = TweetThread.create_simple_tweet(
        content=tweet_content,
        tweet_type="reddit_analysis_report",
        metadata={
            "analysis_timestamp": str(analysis_data["timestamp"]),
            "analysis_id": analysis_data["id"],
            "subreddit": analysis_data["subreddit"],
            "title_used": title,
        },
    )

    # Post the tweet
    try:
        logger.info("Attempting to post Reddit analysis tweet")
        success = send_tweet2(thread, logger=logger, headless=True, verify=False)

        if success:
            logger.info("Successfully posted Reddit analysis tweet")

            # Mark analysis as posted to avoid duplicates
            mark_success = reddit_db.mark_analysis_as_posted(int(analysis_data["id"]))
            if mark_success:
                logger.info(f"Marked Reddit analysis ID {analysis_data['id']} as posted")
            else:
                logger.warning(
                    f"Failed to mark Reddit analysis ID {analysis_data['id']} as posted"
                )

            # Send notification email
            try:
                em.send_email_alert(
                    f"Posted Reddit cross-analysis: {title} (ID: {analysis_data['id']})",
                    "reddit_analysis_report",
                )
                logger.info("Sent email notification")
            except Exception as e:
                logger.warning(f"Failed to send email notification: {e}")
        else:
            logger.error("Failed to post Reddit analysis tweet")

        return success

    except Exception as e:
        logger.error(f"Error posting Reddit analysis tweet: {e}", exc_info=True)
        return False


def main():
    """Main function to post the latest Reddit cross-analysis."""
    parser = argparse.ArgumentParser(
        description="Post the latest Reddit cross-analysis to X.com"
    )
    parser.add_argument(
        "--title",
        type=str,
        help="Custom title for the report (if not provided, will use random nostalgic title)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be posted without actually posting",
    )
    args = parser.parse_args()

    logger.info("Starting Reddit analysis posting process")

    try:
        # Get the latest cross-analysis
        analysis_data = get_latest_reddit_analysis()
        if not analysis_data:
            logger.info("No unposted Reddit cross-analyses found. Exiting.")
            sys.exit(0)

        # Select title
        title = args.title
        if not title:
            import random

            title = random.choice(NEWS_TITLES)

        if args.dry_run:
            # Show what would be posted
            tweet_content = format_reddit_analysis_tweet(analysis_data, title)
            print("\n" + "=" * 60)
            print("DRY RUN - Would post the following tweet:")
            print("=" * 60)
            print(tweet_content)
            print("=" * 60)
            print(f"Character count: {len(tweet_content)}")
            logger.info("Dry run completed")
            sys.exit(0)

        # Post the analysis
        success = post_reddit_analysis_tweet(analysis_data, title)

        if success:
            logger.info("Reddit analysis posting process completed successfully")
        else:
            logger.error("Reddit analysis posting process failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"An error occurred in the main process: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 