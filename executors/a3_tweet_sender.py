#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime, timedelta
import time
import json
import argparse

PROJECT_PATH = os.environ.get("PROJECT_PATH")
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.tweet_db as tweet_db
import utils.tweet as tweet
from workflow.z3_schedule_reply import SelectedTweet, TweetReplyData, create_tweet_reply

logger = setup_logger(__name__, "a3_tweet_sender.log")

def check_and_send_approved_tweets():
    """Check for approved tweets and send them."""
    logger.info("Checking for approved tweets")
    
    # Get approved tweets
    approved_tweets = tweet_db.read_tweet_replies()
    approved_tweets = approved_tweets[approved_tweets['approval_status'] == 'approved']
    
    if approved_tweets.empty:
        logger.info("No approved tweets found")
        return 0
    
    logger.info(f"Found {len(approved_tweets)} approved tweets")
    
    # Process the oldest approved tweet first
    approved_tweet = approved_tweets.sort_values('tstp').iloc[0]
    
    try:
        # Create TweetReplyData object
        meta_data = approved_tweet['meta_data']
        if isinstance(meta_data, str):
            meta_data = json.loads(meta_data)
        
        selected_tweet = SelectedTweet(
            tweet_id=meta_data.get('tweet_id', ''),
            tweet_text=approved_tweet['selected_tweet'],
            response_type=meta_data.get('response_type', 'a'),
            has_media=False  # Default to False if not available
        )
        
        reply_data = TweetReplyData(
            selected_tweet=selected_tweet,
            reply_text=approved_tweet['response'],
            context=meta_data.get('context')
        )
        
        # Create tweet thread
        tweet_thread = create_tweet_reply(reply_data)
        logger.info(f"Sending approved tweet: {tweet_thread.tweets[0].content[:50]}...")
        
        # Send tweet
        for attempt in range(2):
            tweet_success = tweet.send_tweet2(
                tweet_content=tweet_thread,
                logger=logger,
                verify=True,
                headless=False
            )
            if tweet_success:
                # Update status to 'sent'
                tweet_db.update_tweet_reply_status(approved_tweet['id'], 'sent')
                logger.info(f"Successfully sent tweet reply ID: {approved_tweet['id']}")
                return 0
            elif attempt == 0:
                logger.warning("First tweet attempt failed, retrying after 30 seconds...")
                time.sleep(30)
        
        logger.error(f"Failed to send tweet reply ID: {approved_tweet['id']}")
        return 1
        
    except Exception as e:
        logger.error(f"Error sending approved tweet: {str(e)}")
        return 1

def run_continuous_check(check_interval=300, max_runtime=None):
    """ Run continuous check for approved tweets. """
    logger.info(f"Starting continuous check for approved tweets (interval: {check_interval}s)")
    
    start_time = time.time()
    iteration = 0
    
    try:
        while True:
            iteration += 1
            logger.info(f"Check iteration {iteration}")
            
            # Check and send approved tweets
            check_and_send_approved_tweets()
            
            # Check if we've exceeded max runtime
            if max_runtime and (time.time() - start_time) > max_runtime:
                logger.info(f"Reached maximum runtime of {max_runtime}s, exiting")
                break
                
            # Sleep until next check
            logger.info(f"Sleeping for {check_interval} seconds")
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting")
    except Exception as e:
        logger.error(f"Error in continuous check: {str(e)}")
        raise


def main():
    """Main function to check for approved tweets and send them."""
    parser = argparse.ArgumentParser(description="Tweet sender for approved replies")
    parser.add_argument(
        "--continuous", 
        action="store_true", 
        help="Run in continuous mode, checking periodically"
    )
    parser.add_argument(
        "--interval", 
        type=int, 
        default=300, 
        help="Check interval in seconds (default: 300)"
    )
    parser.add_argument(
        "--max-runtime", 
        type=int, 
        default=None, 
        help="Maximum runtime in seconds (default: indefinite)"
    )
    
    args = parser.parse_args()
    
    if args.continuous:
        run_continuous_check(args.interval, args.max_runtime)
        return 0
    else:
        return check_and_send_approved_tweets()

if __name__ == "__main__":
    sys.exit(main()) 