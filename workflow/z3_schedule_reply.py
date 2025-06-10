import os
import sys
# import pandas as pd # Unused
from datetime import datetime, timedelta # Unused
from dataclasses import dataclass
from typing import Optional, Dict, Any
from dotenv import load_dotenv

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.tweet_db as tweet_db
import utils.vector_store as vs
from utils.tweet import TweetThread
from utils.paper_utils import extract_tagged_content
from utils.app_utils import query_llmpedia_new
from utils.notifications import send_tweet_approval_request

## NEW IMPORT
import utils.tweet_data_utils as tdu

logger = setup_logger(__name__, "a2_tweet_replier.log")


@dataclass
class SelectedTweet:
    """Container for selected tweet and its metadata."""

    tweet_id: str
    tweet_text: str
    has_media: bool
    response_type: str  # 'a' for academic, 'b' for funny, 'c' for common-sense
    response_type_analysis: str
    metadata: Dict[str, Any] = None


@dataclass
class TweetReplyData:
    """Container for tweet reply data."""

    selected_tweet: SelectedTweet
    reply_text: str
    context: Optional[str] = None
    metadata: Dict[str, Any] = None


def select_tweet_to_reply(tweets_str: str, recent_discussion_str: str) -> SelectedTweet:
    """Select a tweet to reply to."""
    logger.info("Selecting tweet to reply to.")

    selected_tweet_raw = vs.select_tweet_reply(tweets_str, recent_discussion_str)
    selected_tweet_dict = extract_tagged_content(
        selected_tweet_raw,
        [
            "selected_post",
            "selected_post_id",
            "response_type",
            "response_type_analysis",
            "has_media",
        ],
    )

    logger.info(f"Selected tweet: {selected_tweet_dict['selected_post']}")

    return SelectedTweet(
        tweet_id=selected_tweet_dict["selected_post_id"],
        tweet_text=selected_tweet_dict["selected_post"],
        response_type=selected_tweet_dict["response_type"],
        response_type_analysis=selected_tweet_dict["response_type_analysis"],
        has_media=selected_tweet_dict["has_media"],
    )


def find_related_content(tweet_text: str) -> str:
    """Find related content for the selected tweet."""
    logger.info(f"Finding related content for selected tweet.")

    # Use moved formatting function
    search_query = tdu.format_search_query(tweet_text)

    result = query_llmpedia_new(
        user_question=search_query,
        show_only_sources=False,
        max_sources=25,
        query_llm_model="gemini/gemini-2.5-pro-preview-05-06",
        rerank_llm_model="gemini/gemini-2.0-flash",
        response_llm_model="gemini/gemini-2.5-pro-preview-05-06",
    )

    llmpedia_analysis = result[0]
    logger.info("Found related content")

    return llmpedia_analysis


def generate_reply(
    selected_tweet: SelectedTweet,
    context: str,
    previous_posts: str,
    recent_discussions: str,
) -> str:
    """Generate a reply to the selected tweet."""
    logger.info(f"Generating {selected_tweet.response_type} reply for selected tweet.")

    ## Append media placeholder if tweet has media.
    if selected_tweet.has_media:
        selected_tweet.tweet_text = (
            f"{selected_tweet.tweet_text}\n\n[Media placeholder]"
        )

    # For response type 'b' (funny response)
    if selected_tweet.response_type == "b":
        reply = vs.write_tweet_reply_funny(
            selected_post=selected_tweet.tweet_text,
            summary_of_recent_discussions=recent_discussions,
            previous_posts=previous_posts,
            model="claude-3-7-sonnet-20250219",
            temperature=1,
        )
        reply_dict = extract_tagged_content(reply, ["post_response"])

    # For response type 'c' (common-sense response)
    elif selected_tweet.response_type == "c":
        reply = vs.write_tweet_reply_commonsense(
            selected_post=selected_tweet.tweet_text,
            summary_of_recent_discussions=recent_discussions,
            previous_posts=previous_posts,
            # model="gpt-4.5-preview-2025-02-27",
            model="claude-3-7-sonnet-20250219",
            temperature=1,
        )
        reply_dict = extract_tagged_content(reply, ["post_response"])

    # For response type 'a' (academic response)
    else:  # response_type == "a"
        reply = vs.write_tweet_reply_academic(
            selected_post=selected_tweet.tweet_text,
            context=context,
            summary_of_recent_discussions=recent_discussions,
            previous_posts=previous_posts,
            # model="gpt-4.5-preview-2025-02-27",
            model="claude-3-7-sonnet-20250219",
            temperature=1,
            # thinking={"type": "enabled", "budget_tokens": 1024},
        )
        reply_dict = extract_tagged_content(reply, ["post_response"])

    logger.info(f"Generated reply: {reply_dict['post_response']}")
    return reply_dict["post_response"]


def create_tweet_reply(reply_data: TweetReplyData) -> TweetThread:
    """Create a TweetThread object for the reply."""
    content = reply_data.reply_text

    # Create metadata
    metadata = {
        "original_tweet_id": reply_data.selected_tweet.tweet_id,
        "original_tweet_text": reply_data.selected_tweet.tweet_text,
        "response_type": reply_data.selected_tweet.response_type,
        "generated_at": datetime.now().isoformat(),
    }

    # Create a simple tweet thread
    return TweetThread.create_simple_tweet(
        content=content, tweet_type="tweet_reply", metadata=metadata
    )


def store_reply_data(reply_data: TweetReplyData) -> bool:
    """Store the reply data in the database and send approval request."""
    logger.info(f"Storing reply data for tweet: {reply_data.selected_tweet.tweet_text}")

    metadata = {
        "tweet_id": reply_data.selected_tweet.tweet_id,
        "response_type": reply_data.selected_tweet.response_type,
        "context": reply_data.context,
    }

    # Store the reply with 'pending' approval status
    success = tweet_db.store_tweet_reply(
        selected_tweet=reply_data.selected_tweet.tweet_text,
        response=reply_data.reply_text,
        meta_data=metadata,
        approval_status="pending",
    )

    if success:
        logger.info("Successfully stored reply data.")

        # Get the ID of the stored reply
        # We need to query for the most recent reply with matching content
        recent_replies = tweet_db.read_tweet_replies(
            start_date=datetime.now() - timedelta(minutes=5)
        )

        if not recent_replies.empty:
            # Find the most recent reply with matching content
            matching_replies = recent_replies[
                (
                    recent_replies["selected_tweet"]
                    == reply_data.selected_tweet.tweet_text
                )
                & (recent_replies["response"] == reply_data.reply_text)
            ]

            if not matching_replies.empty:
                # Get the most recent matching reply
                reply_id = matching_replies.iloc[0]["id"]

                # Send approval request
                notification_sent = send_tweet_approval_request(
                    reply_id=reply_id,
                    selected_tweet=reply_data.selected_tweet.tweet_text,
                    reply_text=reply_data.reply_text,
                    response_type=reply_data.selected_tweet.response_type
                )
                # notification_sent = True

                if notification_sent:
                    logger.info(f"Sent approval request for reply ID: {reply_id}")
                else:
                    logger.error("Failed to send approval request")
            else:
                logger.error("Could not find the stored reply in the database")
    else:
        logger.error("Failed to store reply data.")

    return success


def main():
    """Generate a reply to a selected tweet and store it for approval."""
    logger.info("Starting tweet reply process")

    try:
        ## Get previous posts, community posts, and recent discussions.
        previous_posts = tdu.get_previous_posts()
        community_posts = tdu.get_community_posts(sample_size=30)
        recent_discussions = tdu.get_recent_discussions()

        ## Select a tweet to reply to.
        selected_tweet = select_tweet_to_reply(community_posts, recent_discussions)

        ## Find related content for academic replies.
        context = None
        if selected_tweet.response_type == "a":
            context = find_related_content(selected_tweet.tweet_text)

        ## Generate a reply.
        reply_text = generate_reply(
            selected_tweet, context, previous_posts, recent_discussions
        )

        ## Create reply data.
        reply_data = TweetReplyData(
            selected_tweet=selected_tweet, reply_text=reply_text, context=context
        )

        ## Store the reply data and send approval request.
        store_success = store_reply_data(reply_data)
        if not store_success:
            logger.error("Failed to store reply data")
            return 1

        logger.info("Successfully generated and stored tweet reply for approval")
        return 0

    except Exception as e:
        logger.error(f"Error in tweet reply process: {str(e)}")
        raise


if __name__ == "__main__":
    sys.exit(main())