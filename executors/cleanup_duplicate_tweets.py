#!/usr/bin/env python3

"""
Utility script to clean up duplicate pending tweets for papers that have already been posted.
This addresses the issue where the same arxiv code keeps getting selected for tweeting.

Usage:
    python utils/cleanup_duplicate_tweets.py           # Run cleanup
    python utils/cleanup_duplicate_tweets.py --dry-run # Check for duplicates without cleaning
"""

import os
import sys
import argparse
from dotenv import load_dotenv

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.tweet_db as tweet_db

logger = setup_logger(__name__, "cleanup_duplicate_tweets.log")

def main():
    """Main function to clean up duplicate pending tweets."""
    parser = argparse.ArgumentParser(description="Clean up duplicate pending tweets for already posted papers.")
    parser.add_argument("--dry-run", action="store_true", help="Check for duplicates without cleaning them up")
    args = parser.parse_args()
    
    action = "dry run check" if args.dry_run else "cleanup"
    logger.info(f"Starting {action} of duplicate pending tweets...")
    
    try:
        if args.dry_run:
            # Just count duplicates without cleaning
            from utils.db.db_utils import execute_read_query
            count_query = """
            SELECT COUNT(*) as duplicate_count
            FROM pending_tweets pt
            WHERE pt.status = 'pending' 
            AND pt.arxiv_code IN (
                SELECT DISTINCT arxiv_code 
                FROM tweet_reviews 
                WHERE rejected = false
            )
            """
            result = execute_read_query(count_query, as_dataframe=False)
            duplicate_count = result[0][0] if result else 0
            
            if duplicate_count > 0:
                logger.warning(f"Found {duplicate_count} duplicate pending tweets that should be cleaned up.")
                print(f"DRY RUN: Found {duplicate_count} duplicate pending tweets.")
                print("Run without --dry-run to clean them up.")
            else:
                logger.info("No duplicate pending tweets found.")
                print("DRY RUN: No duplicates found.")
        else:
            # Run actual cleanup
            rejected_count = tweet_db.cleanup_duplicate_pending_tweets()
            
            if rejected_count > 0:
                logger.info(f"Cleanup completed successfully. Rejected {rejected_count} duplicate pending tweets.")
                print(f"Successfully cleaned up {rejected_count} duplicate pending tweets.")
            else:
                logger.info("Cleanup completed. No duplicates found or all were already handled.")
                print("No duplicates found to clean up.")
                
    except Exception as e:
        logger.error(f"Error during {action} process: {e}", exc_info=True)
        print(f"Error during {action}: {e}")
        sys.exit(1)
    
    logger.info(f"{action.capitalize()} process finished.")

if __name__ == "__main__":
    main() 