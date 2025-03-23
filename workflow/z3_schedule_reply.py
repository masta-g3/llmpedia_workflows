import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional,  Dict, Any
from dotenv import load_dotenv

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.tweet_db as tweet_db
import utils.vector_store as vs
from utils.tweet import TweetThread
from utils.paper_utils import extract_tagged_content
from utils.app_utils import query_llmpedia_new
from utils.notifications import send_tweet_approval_request

logger = setup_logger(__name__, "a2_tweet_replier.log")


@dataclass
class SelectedTweet:
    """Container for selected tweet and its metadata."""
    tweet_id: str
    tweet_text: str
    has_media: bool
    response_type: str  # 'a' for academic, 'b' for funny, 'c' for common-sense


@dataclass
class TweetReplyData:
    """Container for tweet reply data."""
    selected_tweet: SelectedTweet
    reply_text: str
    context: Optional[str] = None
    metadata: Dict[str, Any] = None


# ---- Formatting Functions ----

def format_tweet_thread(df: pd.DataFrame) -> str:
    """Format DataFrame of tweets and responses into a readable thread format."""
    formatted_thread = []
    
    # Sort by timestamp to maintain conversation flow
    df_sorted = df.sort_values('tstp')
    
    for _, row in df_sorted.iterrows():
        # Format original tweet
        formatted_thread.append("<selected_tweet>")
        formatted_thread.append(row['selected_tweet'].strip())
        formatted_thread.append("</selected_tweet>")
        
        # Format response 
        formatted_thread.append("<tweet_response>")
        formatted_thread.append(row['response'].strip())
        formatted_thread.append("</tweet_response>")
        formatted_thread.append("------------------")  # Separator between tweet-response pairs
    
    return "\n".join(formatted_thread)


def format_community_tweet(tweet_id: str, timestamp: str, username: str, text: str, has_media: bool = False) -> str:
    """Format a single community tweet into XML format."""
    tweet_parts = [
        "<tweet>",
        f"<id>{tweet_id}</id>",
        f"<tstp>{timestamp}</tstp>",
        f"<author>{username}</author>",
        f"<has_media>{str(has_media).lower()}</has_media>",
        "<text>",
        text,
        "</text>",
        "</tweet>"
    ]
    return "\n".join(tweet_parts)


def format_discussion_summary(timestamp: str, summary: str) -> str:
    """Format a discussion summary into XML format."""
    parts = [
        "<discussion_summary>",
        f"<timestamp>{timestamp}</timestamp>",
        "<summary>",
        summary.strip(),
        "</summary>",
        "</discussion_summary>"
    ]
    return "\n".join(parts)


def format_search_query(tweet_text: str) -> str:
    """Format a search query for LLMpedia."""
    return f"""I am trying to find LLM papers from 2024 onwards that could help me build an insightful reply to this tweet:

<selected_tweet>
{tweet_text}
</selected_tweet>
"""

# ---- Data Retrieval Functions ----

def get_previous_posts(days: int = 10, max_posts: int = 30) -> str:
    """Get previous posts from the database."""
    threads_df = tweet_db.read_tweet_replies(start_date=datetime.now() - timedelta(days=days))
    threads_df.sort_values(by="tstp", ascending=False, inplace=True)
    threads_df = threads_df[threads_df["approval_status"] == "approved"]
    
    return format_tweet_thread(threads_df.head(max_posts))


def get_community_posts(hours: int = 48, sample_size: int = 50) -> str:
    """Get community posts from the database."""
    tweets_df = tweet_db.read_tweets(
        start_date=datetime.now() - timedelta(hours=hours), 
        end_date=datetime.now()
    )
    
    # Clean and prepare data
    tweets_df.drop_duplicates(subset="text", keep="first", inplace=True)
    tweets_df["tstp"] = pd.to_datetime(tweets_df["tstp"], unit="s")
    tweets_df["date"] = pd.to_datetime(tweets_df["tstp"].dt.date)
    tweets_df["date_hour"] = tweets_df["tstp"].dt.floor('H')
    
    # Sample tweets
    tweets_df = tweets_df.sample(n=min(sample_size, len(tweets_df))).reset_index(drop=True)
    
    # Format tweets using the dedicated formatting function
    tweets_raw = []
    for _, row in tweets_df.iterrows():
        timestamp = row["tstp"].strftime("%Y-%m-%d %H:%M")
        username = row["username"]
        text = row["text"]
        tweet_id = row["id"]
        has_media = row.get("has_media", False)  # Get has_media with default False if not present
        tweets_raw.append(format_community_tweet(tweet_id, timestamp, username, text, has_media))
    
    return "\n".join(tweets_raw)


def get_recent_discussions(max_discussions: int = 5, days: int = 2) -> str:
    """Get recent discussions from the database."""
    discussion_df = tweet_db.read_last_n_tweet_analyses(n=max_discussions)
    discussion_df = discussion_df[discussion_df["tstp"] > datetime.now() - timedelta(days=days)]
    
    # Format discussions using the dedicated formatting function
    discussions = []
    for _, row in discussion_df.iterrows():
        timestamp = row["tstp"].strftime("%Y-%m-%d %H:%M")
        discussions.append(format_discussion_summary(timestamp, row["response"]))
    
    return "\n".join(discussions)


# ---- Core Processing Functions ----

def select_tweet_to_reply(tweets_str: str, recent_discussion_str: str) -> SelectedTweet:
    """Select a tweet to reply to."""
    logger.info("Selecting tweet to reply to.")
    
    selected_tweet_raw = vs.select_tweet_reply(tweets_str, recent_discussion_str)
    selected_tweet_dict = extract_tagged_content(
        selected_tweet_raw, ["selected_post", "selected_post_id", "response_type", "has_media"]
    )
    
    logger.info(f"Selected tweet: {selected_tweet_dict['selected_post']}")
    
    return SelectedTweet(
        tweet_id=selected_tweet_dict["selected_post_id"],
        tweet_text=selected_tweet_dict["selected_post"],
        response_type=selected_tweet_dict["response_type"],
        has_media=selected_tweet_dict["has_media"]
    )


def find_related_content(tweet_text: str) -> str:
    """Find related content for the selected tweet."""
    logger.info(f"Finding related content for selected tweet.")
    
    search_query = format_search_query(tweet_text)
    
    result = query_llmpedia_new(
        user_question=search_query,
        show_only_sources=False,
        max_sources=25,
    )
    
    llmpedia_analysis = result[0]
    logger.info("Found related content")
    
    return llmpedia_analysis


def generate_reply(selected_tweet: SelectedTweet, context: str, previous_posts: str, recent_discussions: str) -> str:
    """Generate a reply to the selected tweet."""
    logger.info(f"Generating {selected_tweet.response_type} reply for selected tweet.")

    ## Append media placeholder if tweet has media.
    if selected_tweet.has_media:
        selected_tweet.tweet_text = f"{selected_tweet.tweet_text}\n\n[Media placeholder]"

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
            model="claude-3-7-sonnet-20250219",
            temperature=1,
        )
        reply_dict = extract_tagged_content(reply, ["post_response"])
    
    logger.info(f"Generated reply: {reply_dict['post_response']}")
    return reply_dict["post_response"]


# ---- The following functions extend beyond what's shown in the notebook ----

def create_tweet_reply(reply_data: TweetReplyData) -> TweetThread:
    """Create a TweetThread object for the reply."""
    content = reply_data.reply_text
    
    # Create metadata
    metadata = {
        "original_tweet_id": reply_data.selected_tweet.tweet_id,
        "original_tweet_text": reply_data.selected_tweet.tweet_text,
        "response_type": reply_data.selected_tweet.response_type,
        "generated_at": datetime.now().isoformat()
    }
    
    # Create a simple tweet thread
    return TweetThread.create_simple_tweet(
        content=content,
        tweet_type="tweet_reply",
        metadata=metadata
    )


def store_reply_data(reply_data: TweetReplyData) -> bool:
    """Store the reply data in the database and send approval request."""
    logger.info(f"Storing reply data for tweet: {reply_data.selected_tweet.tweet_text}")
    
    metadata = {
        "tweet_id": reply_data.selected_tweet.tweet_id,
        "response_type": reply_data.selected_tweet.response_type,
        "context": reply_data.context
    }
    
    # Store the reply with 'pending' approval status
    success = tweet_db.store_tweet_reply(
        selected_tweet=reply_data.selected_tweet.tweet_text,
        response=reply_data.reply_text,
        meta_data=metadata,
        approval_status="pending"
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
                (recent_replies['selected_tweet'] == reply_data.selected_tweet.tweet_text) & 
                (recent_replies['response'] == reply_data.reply_text)
            ]
            
            if not matching_replies.empty:
                # Get the most recent matching reply
                reply_id = matching_replies.iloc[0]['id']
                
                # Send approval request
                notification_sent = send_tweet_approval_request(
                    reply_id=reply_id,
                    selected_tweet=reply_data.selected_tweet.tweet_text,
                    reply_text=reply_data.reply_text,
                    response_type=reply_data.selected_tweet.response_type
                )
                
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
        # Get previous posts, community posts, and recent discussions
        previous_posts = get_previous_posts()
        community_posts = get_community_posts()
        recent_discussions = get_recent_discussions()
        
        # Select a tweet to reply to
        selected_tweet = select_tweet_to_reply(community_posts, recent_discussions)
        
        # Find related content for academic replies
        context = None
        if selected_tweet.response_type == "a":
            context = find_related_content(selected_tweet.tweet_text)
        
        # Generate a reply
        reply_text = generate_reply(selected_tweet, context, previous_posts, recent_discussions)
        
        # Create reply data
        reply_data = TweetReplyData(
            selected_tweet=selected_tweet,
            reply_text=reply_text,
            context=context
        )
        
        # Store the reply data and send approval request
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