# Functions for retrieving and formatting tweet-related data

import pandas as pd
from datetime import datetime, timedelta
import utils.db.tweet_db as tweet_db

# ---- Formatting Functions ----

def format_tweet_thread(df: pd.DataFrame) -> str:
    """Format DataFrame of tweets and responses into a readable thread format."""
    formatted_thread = []

    # Sort by timestamp to maintain conversation flow
    df_sorted = df.sort_values("tstp")

    for _, row in df_sorted.iterrows():
        # Format original tweet
        formatted_thread.append("<selected_tweet>")
        formatted_thread.append(row["selected_tweet"].strip())
        formatted_thread.append("</selected_tweet>")

        # Format response
        formatted_thread.append("<tweet_response>")
        formatted_thread.append(row["response"].strip())
        formatted_thread.append("</tweet_response>")
        formatted_thread.append(
            "------------------"
        )  # Separator between tweet-response pairs

    return "\n".join(formatted_thread)

def format_community_tweet(
    tweet_id: str, timestamp: str, username: str, text: str, has_media: bool = False
) -> str:
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
        "</tweet>",
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
        "</discussion_summary>",
    ]
    return "\n".join(parts)

def format_search_query(tweet_text: str) -> str:
    """Format a search query for LLMpedia."""
    return f"""I am trying to find LLM papers from 2025 onwards that could help me build an insightful reply to this tweet:

<selected_tweet>
{tweet_text}
</selected_tweet>
"""

# ---- Data Retrieval Functions ----

def get_previous_posts(days: int = 10, max_posts: int = 30) -> str:
    """Get previous posts from the database."""
    threads_df = tweet_db.read_tweet_replies(
        start_date=datetime.now() - timedelta(days=days)
    )
    threads_df.sort_values(by="tstp", ascending=False, inplace=True)
    threads_df = threads_df[threads_df["approval_status"] == "approved"]

    # Calls local formatting function
    return format_tweet_thread(threads_df.head(max_posts))

def get_community_posts(hours: int = 48, sample_size: int = 50) -> str:
    """Get community posts from the database."""
    tweets_df = tweet_db.read_tweets(
        start_date=datetime.now() - timedelta(hours=hours), end_date=datetime.now()
    )

    # Clean and prepare data
    tweets_df.drop_duplicates(subset="text", keep="first", inplace=True)
    tweets_df["tstp"] = pd.to_datetime(tweets_df["tstp"], unit="s")
    tweets_df["date"] = pd.to_datetime(tweets_df["tstp"].dt.date)
    tweets_df["date_hour"] = tweets_df["tstp"].dt.floor("H")

    # Sample tweets
    tweets_df = tweets_df.sample(n=min(sample_size, len(tweets_df))).reset_index(
        drop=True
    )

    # Format tweets using the dedicated formatting function
    tweets_raw = []
    for _, row in tweets_df.iterrows():
        timestamp = row["tstp"].strftime("%Y-%m-%d %H:%M")
        username = row["username"]
        text = row["text"]
        tweet_id = row["id"]
        has_media = row.get(
            "has_media", False
        )  # Get has_media with default False if not present
        # Calls local formatting function
        tweets_raw.append(
            format_community_tweet(tweet_id, timestamp, username, text, has_media)
        )

    return "\n".join(tweets_raw)

def get_recent_discussions(max_discussions: int = 5, days: int = 2) -> str:
    """Get recent discussions from the database."""
    discussion_df = tweet_db.read_last_n_tweet_analyses(n=max_discussions)
    discussion_df = discussion_df[
        discussion_df["tstp"] > datetime.now() - timedelta(days=days)
    ]

    # Format discussions using the dedicated formatting function
    discussions = []
    for _, row in discussion_df.iterrows():
        timestamp = row["tstp"].strftime("%Y-%m-%d %H:%M")
        # Calls local formatting function
        discussions.append(format_discussion_summary(timestamp, row["response"]))

    return "\n".join(discussions) 