#!/usr/bin/env python3

"""
Workflow script to:
1. Fetch pending tweet candidates from the database.
2. Use an LLM to select the best candidate.
3. Post the selected tweet thread to X.com.
4. Update the status of the tweet in the database.
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict

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
import utils.db.tweet_db as tweet_db
import utils.vector_store as vs
import utils.notifications as em
from utils.tweet import send_tweet2, TweetThread
from utils.image_utils import ImageManager
from utils.db.tweet_db import PendingTweetStatus

# Constants
DEFAULT_CANDIDATE_LIMIT = 15
DEFAULT_SELECTION_MODEL = "claude-3-7-sonnet-20250219"
DATA_PATH = os.path.join(PROJECT_PATH, "data")
IMG_PATH = os.path.join(DATA_PATH, "arxiv_art")

logger = setup_logger(__name__, "z4_select_and_post_tweet.log")


def fetch_and_prepare_candidates(limit: int) -> List[Dict]:
    """Fetches pending tweets and prepares them for LLM selection."""
    logger.info(
        f"Fetching up to {limit} pending tweets (excluding already posted papers)."
    )
    ## No try/except here per plan; let DB errors fail the script
    pending_tweets_df = tweet_db.fetch_pending_tweets(limit=limit)

    if pending_tweets_df.empty:
        logger.info("No pending tweets found (excluding already posted papers).")
        return []

    logger.info(
        f"Fetched {len(pending_tweets_df)} pending tweets for papers not yet posted."
    )

    candidates_for_llm = []
    for tweet_id, row in pending_tweets_df.iterrows():
        try:
            thread_data = json.loads(row["thread_data_json"])
            # Validate basic structure and get first tweet
            if (
                not isinstance(thread_data, dict)
                or "tweets" not in thread_data
                or not thread_data["tweets"]
            ):
                logger.warning(
                    f"Skipping tweet ID {tweet_id}: Invalid or empty thread data."
                )
                continue

            ## Find the tweet with position 0 (or the first one if none have position 0)
            first_tweet_content = ""
            min_pos = float("inf")
            first_tweet = None
            for tweet in thread_data["tweets"]:
                if tweet.get("position") == 0:
                    first_tweet = tweet
                    break
                if tweet.get("position", float("inf")) < min_pos:
                    min_pos = tweet.get("position", float("inf"))
                    first_tweet = tweet

            if first_tweet:
                first_tweet_content = first_tweet.get("content", "")
            else:
                logger.warning(
                    f"Skipping tweet ID {tweet_id}: Could not determine first tweet."
                )
                continue

            candidates_for_llm.append(
                {
                    "id": tweet_id,
                    "arxiv_code": row["arxiv_code"],
                    "tweet_type": row["tweet_type"],
                    "first_tweet_content": first_tweet_content,
                }
            )
        except json.JSONDecodeError:
            logger.error(
                f"Skipping tweet ID {tweet_id}: Failed to parse thread_data_json."
            )
        except Exception as e:
            logger.error(
                f"Skipping tweet ID {tweet_id}: Unexpected error processing data: {e}",
                exc_info=True,
            )

    logger.info(
        f"Prepared {len(candidates_for_llm)} valid candidates for LLM selection."
    )
    return candidates_for_llm


def select_candidate(
    candidates: List[Dict], model: str, recent_posted_tweets: Optional[List[str]] = None
) -> Optional[int]:
    """Uses an LLM to select the best candidate from the list."""
    selected_id = None
    try:
        logger.info(
            f"Calling LLM ({model}) to select the best tweet from {len(candidates)} candidates."
        )
        selected_id = vs.select_best_pending_tweet(
            candidates,
            model=model,
            logger=logger,
            recent_posted_tweets=recent_posted_tweets,
        )
    except Exception as e:
        logger.error(f"LLM selection call failed: {e}", exc_info=True)
        return None

    if selected_id is None:
        logger.error("LLM did not select a tweet.")
        return None

    logger.info(f"LLM selected tweet ID: {selected_id}")
    return selected_id


def reject_other_candidates(all_candidates: List[Dict], selected_id: int):
    """Updates the status of non-selected candidates to 'rejected'."""
    rejected_count = 0
    for cand in all_candidates:
        if cand["id"] != selected_id:
            rej_success = tweet_db.update_pending_tweet_status(
                cand["id"], PendingTweetStatus.REJECTED.value
            )
            if rej_success:
                rejected_count += 1
            else:
                logger.warning(
                    f"Failed to update status to 'rejected' for tweet ID {cand['id']}."
                )
    logger.info(f"Updated status to 'rejected' for {rejected_count} other candidates.")


def handle_successful_post(selected_id: int, thread: TweetThread):
    """Handles database updates and notifications after a successful post."""
    logger.info(f"Successfully posted tweet for ID {selected_id}.")
    try:
        # Update status to 'posted'
        update_posted_success = tweet_db.update_pending_tweet_status(
            selected_id,
            PendingTweetStatus.POSTED.value,
            timestamp_field="posting_timestamp",
        )
        if not update_posted_success:
            logger.warning(
                f"Failed to update status to 'posted' for tweet ID {selected_id} after successful post."
            )

        # Log to tweet_reviews
        first_tweet_content = thread.tweets[0].content if thread.tweets else ""
        review_success = tweet_db.insert_tweet_review(
            arxiv_code=thread.arxiv_code,
            review=first_tweet_content,
            tstp=datetime.now(),
            tweet_type=thread.tweet_type,
            rejected=False,
        )
        if not review_success:
            logger.warning(
                f"Failed to insert tweet review for {thread.arxiv_code} after successful post."
            )

        # Send email alert
        em.send_email_alert(first_tweet_content, thread.arxiv_code)
        logger.info(
            f"Sent email alert for successfully posted tweet {selected_id} (Arxiv: {thread.arxiv_code})."
        )
    except Exception as e:
        # Log errors in post-posting actions but don't fail the script as tweet *was* posted.
        logger.error(
            f"Error during post-posting actions for tweet ID {selected_id}: {e}",
            exc_info=True,
        )


def main():
    """Main function to select and post the best pending tweet."""
    parser = argparse.ArgumentParser(
        description="Select the best pending tweet and post it."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_CANDIDATE_LIMIT,
        help=f"Maximum number of pending tweets to fetch for selection (default: {DEFAULT_CANDIDATE_LIMIT}).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_SELECTION_MODEL,
        help=f"LLM model to use for selection (default: {DEFAULT_SELECTION_MODEL}).",
    )
    args = parser.parse_args()

    logger.info("Starting tweet selection and posting process...")

    ## 1. Fetch and Prepare Candidates
    candidates = fetch_and_prepare_candidates(args.limit)
    if not candidates:
        logger.info("No valid candidates found or prepared. Exiting.")
        sys.exit(0)

    ## 2. Select Candidate via LLM
    ## Fetch recent posts to provide context for selection
    recent_posts = tweet_db.read_recent_posted_tweets(n=20)
    logger.info(f"Providing {len(recent_posts)} recent posts to LLM for context.")

    selected_id = select_candidate(
        candidates, args.model, recent_posted_tweets=recent_posts
    )
    if selected_id is None:
        ## Errors already logged in select_candidate
        sys.exit(1)

    ## 3. Fetch Full Thread for Selected Candidate
    ## No try/except per plan; let DB errors fail
    selected_thread: Optional[TweetThread] = tweet_db.get_pending_tweet_thread(
        selected_id
    )
    if selected_thread is None:
        logger.error(
            f"Failed to retrieve TweetThread for selected ID {selected_id} (was it deleted?). Updating status to error."
        )
        tweet_db.update_pending_tweet_status(
            selected_id, PendingTweetStatus.ERROR.value
        )
        sys.exit(1)
    logger.info(
        f"Successfully retrieved full TweetThread for ID {selected_id} (Arxiv: {selected_thread.arxiv_code})"
    )

    ## 4. Update Status to 'Selected' and Reject Others
    ## No try/except per plan; let DB errors fail
    update_success = tweet_db.update_pending_tweet_status(
        selected_id,
        PendingTweetStatus.SELECTED.value,
        timestamp_field="selection_timestamp",
    )
    if not update_success:
        logger.error(
            f"Failed to update status to 'selected' for tweet ID {selected_id}. Exiting to prevent posting."
        )
        sys.exit(1)
    logger.info(f"Updated status to 'selected' for tweet ID {selected_id}.")

    # reject_other_candidates(candidates, selected_id)

    ## 5. Attempt to Post Tweet
    image_manager = ImageManager(DATA_PATH)
    post_success = False
    try:
        logger.info(
            f"Attempting to post tweet for ID {selected_id} (Arxiv: {selected_thread.arxiv_code})."
        )
        post_success = send_tweet2(
            selected_thread,
            logger,
            tweet_image_path=IMG_PATH,
            headless=True,
            verify=False,
        )
    except Exception as e:
        logger.error(
            f"Error occurred during tweet posting for ID {selected_id}: {e}",
            exc_info=True,
        )
        tweet_db.update_pending_tweet_status(
            selected_id, PendingTweetStatus.ERROR.value
        )
        sys.exit(1)

    ## 6. Handle Post-Posting Actions
    if post_success:
        handle_successful_post(selected_id, selected_thread)
    else:
        logger.error(
            f"Failed to post tweet for ID {selected_id}. Updating status to 'error'."
        )
        tweet_db.update_pending_tweet_status(
            selected_id, PendingTweetStatus.ERROR.value
        )
        sys.exit(1)

    logger.info("Tweet selection and posting process finished.")


if __name__ == "__main__":
    main()
