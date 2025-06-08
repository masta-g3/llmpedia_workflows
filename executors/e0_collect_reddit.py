import os
import sys
import logging
import argparse
from datetime import datetime

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
from utils.reddit import collect_llm_subreddit_data
import utils.db.db_utils as db_utils
import utils.db.reddit_db as reddit_db

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Collect Reddit posts and comments")
    parser.add_argument("--start-date", type=str, help="Start date in YYYY-MM-DD HH:MM:SS format")
    parser.add_argument("--end-date", type=str, help="End date in YYYY-MM-DD HH:MM:SS format")
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logger(__name__, "reddit_collector.log")
    logger.info("Starting Reddit collection process")
    
    ## Log date range if specified
    if args.start_date or args.end_date:
        date_info = f"from {args.start_date}" if args.start_date else ""
        date_info += f" to {args.end_date}" if args.end_date else " to now"
        logger.info(f"Collection date range: {date_info}")
    
    # Create engine once for reuse
    engine = db_utils.get_db_engine()
    
    total_posts_stored = 0
    total_comments_stored = 0
    
    # Collect from Tier 1 subreddits (high priority) by default
    for batch_data in collect_llm_subreddit_data(
        priority_filter=1,  # Only Tier 1 subreddits
        posts_per_subreddit=100,  # Increased from 50 for daily workflow
        comments_per_post=10,
        start_date=args.start_date,
        end_date=args.end_date,
        logger=logger
    ):
        subreddit = batch_data["subreddit"]
        posts = batch_data["posts"]
        comments = batch_data["comments"]
        
        # Store posts
        if posts:
            success = reddit_db.store_reddit_posts(posts, logger, engine)
            if success:
                total_posts_stored += len(posts)
                logger.info(f"Stored {len(posts)} posts from r/{subreddit}")
        
        # Store comments
        if comments:
            success = reddit_db.store_reddit_comments(comments, logger, engine)
            if success:
                total_comments_stored += len(comments)
                logger.info(f"Stored {len(comments)} comments from r/{subreddit}")
        
        logger.info(f"Completed r/{subreddit}. Total so far: {total_posts_stored} posts, {total_comments_stored} comments")
    
    logger.info(f"Reddit collection process completed. Total stored: {total_posts_stored} posts, {total_comments_stored} comments")

if __name__ == "__main__":
    main() 