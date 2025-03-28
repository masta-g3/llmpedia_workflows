#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime, timedelta
import pandas as pd

PROJECT_PATH = os.environ.get("PROJECT_PATH")
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.paper_db as paper_db
import utils.app_utils as au
import utils.tweet as tweet
import utils.vector_store as vector_store
from utils.tweet import TweetThread

logger = setup_logger(__name__, "a3_weekly_review_tweet.log")

def create_weekly_review_tweet(weekly_content: str, weekly_highlight: str, date_str: str, num_papers_str: str) -> TweetThread:
    """Create a TweetThread object for the weekly review tweet."""
    # Generate the tweet content using the LLM
    tweet_content = vector_store.write_weekly_review_post(
        report_date=date_str,
        weekly_content=weekly_content,
        weekly_highlight=weekly_highlight,
        num_papers_str=num_papers_str,
        llm_model="gemini/gemini-2.5-pro-exp-03-25",
        temperature=1
    )
    
    # Create metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "weekly_review_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    }
    
    # Create the tweet thread
    return TweetThread.create_simple_tweet(
        content=tweet_content,
        tweet_type="weekly_review",
        metadata=metadata
    )

def main():
    """Generate and send weekly review tweet."""
    logger.info("Starting weekly review tweet process")
    
    try:
        # Get the date for this week (Monday)
        today = datetime.now().date()
        days_since_monday = today.weekday()
        current_monday = today - timedelta(days=days_since_monday)
        date_str = current_monday.strftime("%Y-%m-%d")
        date_str = "2025-03-10"
        
        logger.info(f"Fetching weekly review content for week of {date_str}")
        
        # Check if the weekly content exists for this week
        if not paper_db.check_weekly_summary_exists(date_str):
            logger.info("No weekly content found for this week, exiting")
            return 2
        
        # Get the weekly content
        weekly_content_inputs = paper_db.get_weekly_summary_inputs(date_str)
        num_papers_str = str(len(weekly_content_inputs))+"+"
        weekly_content, weekly_highlight, _ = au.get_weekly_summary(date_str)
        
        if not weekly_content or not weekly_highlight:
            logger.error("Failed to retrieve weekly content or highlight")
            return 1
        
        logger.info("Successfully retrieved weekly content and highlight")
        
        # Create tweet thread
        tweet_thread = create_weekly_review_tweet(weekly_content, weekly_highlight, date_str, num_papers_str)
        logger.info(f"Generated tweet content: {tweet_thread.tweets[0].content}")
        
        # Try sending tweet with one retry
        for attempt in range(2):
            tweet_success = tweet.send_tweet2(
                tweet_content=tweet_thread,
                logger=logger,
                verify=True,
                headless=False
            )
            if tweet_success:
                break
            elif attempt == 0:
                logger.warning("First tweet attempt failed, retrying after 30 seconds...")
                import time
                time.sleep(30)
        
        if tweet_success:
            logger.info("Successfully sent weekly review tweet")
            return 0
        else:
            logger.error("Failed to send weekly review tweet")
            return 1
        
    except Exception as e:
        logger.error(f"Error in weekly review tweet process: {str(e)}")
        raise

if __name__ == "__main__":
    sys.exit(main()) 