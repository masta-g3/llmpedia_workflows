"""Database operations for tweet-related functionality."""

from datetime import datetime
import pandas as pd
import logging
from typing import Optional, Union, List, Dict
from sqlalchemy.engine import Engine
import json
from enum import Enum
import pytz

from utils.tweet import TweetThread
from .db_utils import (
    execute_read_query,
    execute_write_query,
    get_db_engine,
    simple_select_query,
)


## Enum for pending tweet status
class PendingTweetStatus(Enum):
    PENDING = "pending"
    SELECTED = "selected"
    POSTED = "posted"
    REJECTED = "rejected"
    ERROR = "error"


def store_pending_tweet(
    arxiv_code: str, tweet_type: str, thread: TweetThread
) -> bool:
    """Store a generated TweetThread as a pending tweet."""
    query = """
    INSERT INTO pending_tweets (arxiv_code, tweet_type, thread_data_json, status)
    VALUES (:arxiv_code, :tweet_type, :thread_data_json, :status)
    """
    try:
        thread_json = thread.model_dump_json()
        params = {
            "arxiv_code": arxiv_code,
            "tweet_type": tweet_type,
            "thread_data_json": thread_json,
            "status": PendingTweetStatus.PENDING.value,
        }
        success = execute_write_query(query, params)
        if success:
            logging.info(
                f"Successfully stored pending tweet for {arxiv_code} ({tweet_type})."
            )
        return success
    except Exception as e:
        logging.error(
            f"Error storing pending tweet for {arxiv_code} ({tweet_type}): {str(e)}"
        )
        return False


def fetch_pending_tweets(
    status: str = PendingTweetStatus.PENDING.value, limit: int = 10
) -> pd.DataFrame:
    """Fetch pending tweets excluding those for papers that have already been posted."""
    try:
        # Validate status
        valid_statuses = [s.value for s in PendingTweetStatus]
        if status not in valid_statuses:
            logging.error(f"Invalid status provided: {status}. Must be one of {valid_statuses}")
            return pd.DataFrame()

        ## Use a SQL query that excludes arxiv codes already posted (rejected=false in tweet_reviews)
        query = """
        SELECT pt.id, pt.arxiv_code, pt.tweet_type, pt.thread_data_json
        FROM pending_tweets pt
        WHERE pt.status = :status
        AND pt.arxiv_code NOT IN (
            SELECT DISTINCT tr.arxiv_code 
            FROM tweet_reviews tr 
            WHERE tr.rejected = false
        )
        ORDER BY pt.generation_timestamp ASC
        LIMIT :limit
        """
        
        params = {"status": status, "limit": limit}
        df = execute_read_query(query, params=params, as_dataframe=True)
        
        ## Set index to id for consistency with original function
        if not df.empty and 'id' in df.columns:
            df.set_index('id', inplace=True)
            
        return df
        
    except Exception as e:
        logging.error(f"Error fetching pending tweets excluding posted with status '{status}': {str(e)}")
        return pd.DataFrame()


def update_pending_tweet_status(
    tweet_id: int, new_status: str, timestamp_field: Optional[str] = None
) -> bool:
    """Update the status and optionally a timestamp of a pending tweet."""
    # Validate status
    valid_statuses = [s.value for s in PendingTweetStatus]
    if new_status not in valid_statuses:
        logging.error(f"Invalid new_status provided: {new_status}. Must be one of {valid_statuses}")
        return False

    # Validate timestamp field if provided
    valid_timestamps = ["selection_timestamp", "posting_timestamp"]
    if timestamp_field and timestamp_field not in valid_timestamps:
        logging.error(f"Invalid timestamp_field provided: {timestamp_field}. Must be one of {valid_timestamps}")
        return False

    query = f"""
    UPDATE pending_tweets
    SET status = :status
    {(", " + timestamp_field + " = :timestamp") if timestamp_field else ""}
    WHERE id = :id
    """
    params = {"status": new_status, "id": tweet_id}
    if timestamp_field:
        params["timestamp"] = datetime.now()

    try:
        success = execute_write_query(query, params)
        if success:
            logging.info(
                f"Successfully updated pending tweet ID {tweet_id} to status '{new_status}'"
                f"{' and set ' + timestamp_field if timestamp_field else ''}."
            )
        else:
            logging.warning(f"Failed to update status for pending tweet ID {tweet_id}.") # Changed to warning as it might not be critical failure always
        return success
    except Exception as e:
        logging.error(
            f"Error updating status for pending tweet ID {tweet_id} to '{new_status}': {str(e)}"
        )
        return False


def get_pending_tweet_thread(tweet_id: int) -> Optional[TweetThread]:
    """Retrieve a specific pending tweet and parse its thread data."""
    try:
        result_df = simple_select_query(
            table="pending_tweets",
            select_cols=["thread_data_json"],
            conditions={"id": tweet_id},
            index_col=None,
        )
        if result_df.empty:
            logging.warning(f"No pending tweet found with ID {tweet_id}.")
            return None

        thread_json = result_df.iloc[0]["thread_data_json"]
        thread = TweetThread.model_validate_json(thread_json)
        return thread
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON for tweet ID {tweet_id}: {str(e)}")
        return None
    except Exception as e: ## Catch potential Pydantic validation errors too
        logging.error(f"Error retrieving or parsing pending tweet thread ID {tweet_id}: {str(e)}")
        return None


def store_tweets(tweets: List[Dict], logger: logging.Logger, engine: Engine) -> bool:
    """Store tweets in the database."""
    try:
        for tweet in tweets:
            # Add collection timestamp
            tweet["tstp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Insert tweet with all available metrics
            query = """
                INSERT INTO llm_tweets (
                    text, author, username, link, tstp, tweet_timestamp,
                    reply_count, repost_count, like_count, view_count, bookmark_count,
                    has_media, is_verified, arxiv_code
                )
                VALUES (
                    :text, :author, :username, :link, :tstp, :tweet_timestamp,
                    :reply_count, :repost_count, :like_count, :view_count, :bookmark_count,
                    :has_media, :is_verified, :arxiv_code
                )
                ON CONFLICT (link) DO NOTHING;
            """

            # Ensure all fields have default values if not present
            tweet_data = {
                "text": tweet.get("text", ""),
                "author": tweet.get("author", ""),
                "username": tweet.get("username", ""),
                "link": tweet.get("link", ""),
                "tstp": tweet.get("tstp"),
                "tweet_timestamp": tweet.get("tweet_timestamp"),
                "reply_count": tweet.get("reply_count", 0),
                "repost_count": tweet.get("repost_count", 0),
                "like_count": tweet.get("like_count", 0),
                "view_count": tweet.get("view_count", 0),
                "bookmark_count": tweet.get("bookmark_count", 0),
                "has_media": tweet.get("has_media", False),
                "is_verified": tweet.get("is_verified", False),
                "arxiv_code": tweet.get("arxiv_code"),
            }

            execute_write_query(query, tweet_data)

        logger.info(f"Successfully stored {len(tweets)} tweets")
        return True
    except Exception as e:
        logger.error(f"Error storing tweets: {str(e)}")
        return False


def read_tweets(
    arxiv_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Read tweets from the database with optional filtering.

    Args:
        arxiv_code: Optional paper identifier
        start_date: Optional start date as string ('2024-01-26' or '2024-01-26 15:33:14')
        end_date: Optional end date as string ('2024-01-26' or '2024-01-26 15:33:14')
    """
    try:
        conditions = {}
        if arxiv_code:
            conditions["arxiv_code"] = arxiv_code

        if start_date:
            try:
                conditions["tstp >= "] = pd.to_datetime(start_date)
            except ValueError as e:
                logging.error(f"Invalid start_date format: {str(e)}")
                return pd.DataFrame()

        if end_date:
            try:
                conditions["tstp <= "] = pd.to_datetime(end_date)
            except ValueError as e:
                logging.error(f"Invalid end_date format: {str(e)}")
                return pd.DataFrame()

        return simple_select_query(
            table="llm_tweets",
            conditions=conditions if conditions else None,
            index_col=None,  # Don't set an index for tweets
        )
    except Exception as e:
        logging.error(f"Error reading tweets from database: {str(e)}")
        return pd.DataFrame()


def store_tweet_analysis(
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
    unique_count: int,
    thinking_process: str,
    response: str,
    referenced_tweets: Optional[Dict] = None,
) -> bool:
    """Store tweet analysis results in the database."""
    try:
        query = """
            INSERT INTO tweet_analysis 
            (start_date, end_date, unique_tweets, thinking_process, response, referenced_tweets)
            VALUES 
            (:start_date, :end_date, :unique_tweets, :thinking_process, :response, :referenced_tweets)
        """

        params = {
            "start_date": min_date,
            "end_date": max_date,
            "unique_tweets": unique_count,
            "thinking_process": thinking_process,
            "response": response,
            "referenced_tweets": json.dumps(referenced_tweets) if referenced_tweets else None,
        }

        success = execute_write_query(query, params)
        if success:
            logging.info(
                f"Successfully stored analysis results for {min_date.strftime('%Y-%m-%d %H:%M')} to {max_date.strftime('%Y-%m-%d %H:%M')}"
            )
        return success
    except Exception as e:
        logging.error(f"Error storing tweet analysis: {str(e)}")
        return False


def read_last_n_tweet_analyses(n: int = 10) -> pd.DataFrame:
    """Read the last N tweet analyses from the database."""
    return simple_select_query(
        table="tweet_analysis",
        select_cols=["id", "tstp", "thinking_process", "response"],
        order_by="tstp DESC",
        index_col=None,
        conditions={"LIMIT": n},
    )


def get_unposted_tweet_analyses(max_age_hours: int = 3) -> pd.DataFrame:
    """Get tweet analyses that haven't been posted yet and are not too old."""
    from datetime import datetime, timedelta
    import pandas as pd
    import pytz
    
    # Use PST timezone
    pst = pytz.timezone('US/Pacific')
    cutoff_time = datetime.now(pst) - timedelta(hours=max_age_hours)
    
    query = """
        SELECT id, tstp, thinking_process, response, referenced_tweets
        FROM tweet_analysis 
        WHERE posted_at IS NULL 
        AND tstp >= :cutoff_time
        ORDER BY tstp ASC
    """
    # Use execute_read_query with as_dataframe=True
    return execute_read_query(query, {"cutoff_time": cutoff_time}, as_dataframe=True)


def mark_analysis_as_posted(analysis_id: int) -> bool:
    """Mark a tweet analysis as posted by setting posted_at timestamp in PST."""
    from datetime import datetime
    import pytz
    
    try:
        # Use PST timezone
        pst = pytz.timezone('US/Pacific')
        posted_time = datetime.now(pst)
        
        query = """
            UPDATE tweet_analysis 
            SET posted_at = :posted_at
            WHERE id = :analysis_id AND posted_at IS NULL
        """
        
        params = {
            "analysis_id": analysis_id,
            "posted_at": posted_time
        }
        
        success = execute_write_query(query, params)
        if success:
            logging.info(f"Marked analysis ID {analysis_id} as posted at {posted_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        return success
    except Exception as e:
        logging.error(f"Error marking analysis as posted: {str(e)}")
        return False


def get_last_posted_analysis_timestamp() -> Optional[datetime]:
    """Get the timestamp of the last posted analysis for sequencing."""
    try:
        query = """
            SELECT tstp 
            FROM tweet_analysis
            WHERE posted_at IS NOT NULL
            ORDER BY posted_at DESC
            LIMIT 1
        """
        
        # Expecting a list of tuples, or None
        result = execute_read_query(query, as_dataframe=False)
        if result and len(result) > 0 and len(result[0]) > 0:
            # result is like [(datetime_obj,)]
            return result[0][0]
        return None
    except Exception as e:
        logging.error(f"Error getting last posted analysis timestamp: {str(e)}")
        return None


def store_tweet_reply(
    selected_tweet: str, response: str, meta_data: Optional[Dict] = None, 
    approval_status: str = "pending"
) -> bool:
    """Store tweet reply data in the database."""
    try:
        query = """
            INSERT INTO tweet_replies 
            (selected_tweet, response, meta_data, approval_status)
            VALUES 
            (:selected_tweet, :response, :meta_data, :approval_status)
        """

        # Convert meta_data dict to JSON string for PostgreSQL JSONB
        meta_data_json = json.dumps(meta_data) if meta_data is not None else None

        params = {
            "selected_tweet": selected_tweet,
            "response": response,
            "meta_data": meta_data_json,
            "approval_status": approval_status,
        }

        success = execute_write_query(query, params)
        if success:
            logging.info(
                f"Successfully stored tweet reply for tweet: {selected_tweet[:50]}..."
            )
        return success
    except Exception as e:
        logging.error(f"Error storing tweet reply: {str(e)}")
        return False


def read_tweet_replies(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> pd.DataFrame:
    """Read tweet replies from the database with optional date range filtering."""
    try:
        conditions = {}
        if start_date:
            try:
                conditions["tstp >="] = pd.to_datetime(start_date)
            except ValueError as e:
                logging.error(f"Invalid start_date format: {str(e)}")
                return pd.DataFrame()

        if end_date:
            try:
                conditions["tstp <="] = pd.to_datetime(end_date)
            except ValueError as e:
                logging.error(f"Invalid end_date format: {str(e)}")
                return pd.DataFrame()

        return simple_select_query(
            table="tweet_replies",
            conditions=conditions if conditions else None,
            order_by="tstp DESC",
            index_col=None,
        )
    except Exception as e:
        logging.error(f"Error reading tweet replies from database: {str(e)}")
        return pd.DataFrame()


def insert_tweet_review(
    arxiv_code: str,
    review: str,
    tstp: datetime,
    tweet_type: str,
    rejected: bool = False,
) -> bool:
    """ Insert tweet review into the database. """
    try:
        query = """
            INSERT INTO tweet_reviews (arxiv_code, review, tstp, tweet_type, rejected)
            VALUES (:arxiv_code, :review, :tstp, :tweet_type, :rejected)
        """

        params = {
            "arxiv_code": arxiv_code,
            "review": review,
            "tstp": tstp,
            "tweet_type": tweet_type,
            "rejected": rejected,
        }

        success = execute_write_query(query, params)
        if success:
            logging.info(f"Successfully stored tweet review for {arxiv_code}.")
        return success
    except Exception as e:
        logging.error(f"Error inserting tweet review: {str(e)}")
        return False

def load_tweet_insights(arxiv_code: Optional[str] = None, drop_rejected: bool = False) -> pd.DataFrame:
    """Load tweet insights from the database."""
    conditions = {
        "tweet_type": [
            "insight_v1", "insight_v2", "insight_v3", 
            "insight_v4", "insight_v5"
        ]
    }
    if arxiv_code:
        conditions["arxiv_code"] = arxiv_code
    if drop_rejected:
        conditions["rejected"] = False

    df = simple_select_query(
        table="tweet_reviews",
        conditions=conditions,
        order_by="tstp DESC",
        select_cols=["arxiv_code", "review", "tstp"]
    )
    
    if not df.empty:
        df.rename(columns={"review": "tweet_insight"}, inplace=True)
        
    return df

def update_tweet_reply_status(reply_id: int, approval_status: str) -> bool:
    """ Update the approval status of a tweet reply. """
    try:
        query = """
            UPDATE tweet_replies
            SET approval_status = :approval_status
            WHERE id = :reply_id
        """
        
        params = {
            "reply_id": reply_id,
            "approval_status": approval_status,
        }
        
        success = execute_write_query(query, params)
        if success:
            logging.info(f"Successfully updated approval status for tweet reply {reply_id} to {approval_status}.")
        return success
    except Exception as e:
        logging.error(f"Error updating tweet reply status: {str(e)}")
        return False


def get_pending_tweet_replies(limit: int = 10) -> pd.DataFrame:
    """ Get pending tweet replies from the database. """
    try:
        query = f"""
            SELECT id, tstp, selected_tweet, response, meta_data, approval_status
            FROM tweet_replies
            WHERE approval_status = 'pending'
            ORDER BY tstp DESC
            LIMIT {limit}
        """
        
        df = execute_read_query(query)
        return df
    except Exception as e:
        logging.error(f"Error getting pending tweet replies: {str(e)}")
        return pd.DataFrame()


def read_recent_posted_tweets(n: int = 5) -> List[str]:
    """Fetch the content of the most recent successfully posted tweets."""
    try:
        ## Fetch the 'review' column (first tweet content) for non-rejected tweets
        df = simple_select_query(
            table="tweet_reviews",
            select_cols=["review"],
            conditions={"rejected": False, "LIMIT": n},
            order_by="tstp DESC", 
            index_col=None,
        )
        return df["review"].tolist() if not df.empty else []
    except Exception as e:
        logging.error(f"Error reading recent posted tweets: {str(e)}")
        return []


def cleanup_duplicate_pending_tweets() -> int:
    """Clean up pending tweets for papers that have already been posted."""
    try:
        ## Use a single SQL UPDATE to mark duplicates as rejected
        query = """
        UPDATE pending_tweets 
        SET status = :rejected_status
        WHERE status = :pending_status
        AND arxiv_code IN (
            SELECT DISTINCT tr.arxiv_code 
            FROM tweet_reviews tr 
            WHERE tr.rejected = false
        )
        """
        
        params = {
            "rejected_status": PendingTweetStatus.REJECTED.value,
            "pending_status": PendingTweetStatus.PENDING.value
        }
        
        ## First count how many will be affected
        count_query = """
        SELECT COUNT(*) as duplicate_count
        FROM pending_tweets pt
        WHERE pt.status = :pending_status 
        AND pt.arxiv_code IN (
            SELECT DISTINCT tr.arxiv_code 
            FROM tweet_reviews tr 
            WHERE tr.rejected = false
        )
        """
        
        count_result = execute_read_query(count_query, params={"pending_status": PendingTweetStatus.PENDING.value}, as_dataframe=False)
        duplicate_count = count_result[0][0] if count_result else 0
        
        if duplicate_count == 0:
            logging.info("No duplicate pending tweets found for already posted papers.")
            return 0
        
        ## Execute the update
        success = execute_write_query(query, params)
        if success:
            logging.info(f"Successfully rejected {duplicate_count} duplicate pending tweets for already posted papers.")
            return duplicate_count
        else:
            logging.error("Failed to execute cleanup update query.")
            return 0
        
    except Exception as e:
        logging.error(f"Error during cleanup of duplicate pending tweets: {str(e)}")
        return 0

def get_tweet_analysis_between(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    select_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Return tweet analysis rows between start and end timestamps."""
    if select_cols is None:
        select_cols = ["tstp", "thinking_process", "response"]
    conditions = {
        "tstp >= ": start_date,
        "tstp <= ": end_date,
    }
    return simple_select_query(
        table="tweet_analysis",
        select_cols=select_cols,
        conditions=conditions,
        order_by="tstp ASC",
        index_col=None,
    )


def get_tweet_urls_by_ids(tweet_ids: List[int]) -> Dict[int, str]:
    """Get tweet URLs for given tweet IDs."""
    if not tweet_ids:
        return {}
    
    try:
        result_df = simple_select_query(
            table="llm_tweets",
            conditions={"id": tweet_ids},
            select_cols=["id", "link"],
            index_col=None
        )
        
        if result_df.empty:
            return {}
        
        # Return dict mapping tweet_id -> link
        return dict(zip(result_df['id'], result_df['link']))
        
    except Exception as e:
        logging.error(f"Error getting tweet URLs by IDs: {str(e)}")
        return {}