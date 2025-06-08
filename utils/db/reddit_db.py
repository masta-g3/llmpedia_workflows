"""Database operations for Reddit-related functionality."""

from datetime import datetime
import pandas as pd
import logging
from typing import Optional, Union, List, Dict
from sqlalchemy.engine import Engine
import json

from .db_utils import (
    execute_read_query,
    execute_write_query,
    get_db_engine,
)


def store_reddit_posts(posts: List[Dict], logger: logging.Logger, engine: Optional[Engine] = None) -> bool:
    """Store Reddit posts in the database."""
    if engine is None:
        engine = get_db_engine()
    
    for post in posts:
        ## Add collection timestamp
        post["tstp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ## Insert post with all available metrics
        query = """
            INSERT INTO reddit_posts (
                reddit_id, subreddit, title, selftext, author, url, permalink,
                tstp, post_timestamp, score, upvote_ratio, num_comments,
                is_self, post_type, flair_text, arxiv_code, metadata
            )
            VALUES (
                :reddit_id, :subreddit, :title, :selftext, :author, :url, :permalink,
                :tstp, :post_timestamp, :score, :upvote_ratio, :num_comments,
                :is_self, :post_type, :flair_text, :arxiv_code, :metadata
            )
            ON CONFLICT (reddit_id) DO NOTHING;
        """

        ## Ensure all fields have default values if not present
        post_data = {
            "reddit_id": post.get("reddit_id", ""),
            "subreddit": post.get("subreddit", ""),
            "title": post.get("title", ""),
            "selftext": post.get("selftext", ""),
            "author": post.get("author", ""),
            "url": post.get("url", ""),
            "permalink": post.get("permalink", ""),
            "tstp": post.get("tstp"),
            "post_timestamp": post.get("post_timestamp"),
            "score": post.get("score", 0),
            "upvote_ratio": post.get("upvote_ratio", None),
            "num_comments": post.get("num_comments", 0),
            "is_self": post.get("is_self", False),
            "post_type": post.get("post_type", ""),
            "flair_text": post.get("flair_text", ""),
            "arxiv_code": post.get("arxiv_code", None),
            "metadata": json.dumps(post.get("metadata", {})) if post.get("metadata") else None,
        }

        success = execute_write_query(query, post_data)
        if not success:
            logger.warning(f"Failed to store post {post_data['reddit_id']}")
            return False

    logger.info(f"Successfully stored {len(posts)} Reddit posts")
    return True


def store_reddit_comments(comments: List[Dict], logger: logging.Logger, engine: Optional[Engine] = None) -> bool:
    """Store Reddit comments in the database."""
    if engine is None:
        engine = get_db_engine()
        
    for comment in comments:
        ## Add collection timestamp
        comment["tstp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ## Insert comment with all available metrics
        query = """
            INSERT INTO reddit_comments (
                reddit_id, post_reddit_id, parent_id, subreddit, author, body,
                tstp, comment_timestamp, score, depth, is_top_level, metadata
            )
            VALUES (
                :reddit_id, :post_reddit_id, :parent_id, :subreddit, :author, :body,
                :tstp, :comment_timestamp, :score, :depth, :is_top_level, :metadata
            )
            ON CONFLICT (reddit_id) DO NOTHING;
        """

        ## Ensure all fields have default values if not present
        comment_data = {
            "reddit_id": comment.get("reddit_id", ""),
            "post_reddit_id": comment.get("post_reddit_id", ""),
            "parent_id": comment.get("parent_id", None),
            "subreddit": comment.get("subreddit", ""),
            "author": comment.get("author", ""),
            "body": comment.get("body", ""),
            "tstp": comment.get("tstp"),
            "comment_timestamp": comment.get("comment_timestamp"),
            "score": comment.get("score", 0),
            "depth": comment.get("depth", 0),
            "is_top_level": comment.get("is_top_level", False),
            "metadata": json.dumps(comment.get("metadata", {})) if comment.get("metadata") else None,
        }

        success = execute_write_query(query, comment_data)
        if not success:
            logger.warning(f"Failed to store comment {comment_data['reddit_id']}")
            return False

    logger.info(f"Successfully stored {len(comments)} Reddit comments")
    return True


def read_reddit_posts(
    subreddit: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Read Reddit posts from the database with optional filtering."""
    query = "SELECT * FROM reddit_posts WHERE 1=1"
    params = {}

    if subreddit:
        query += " AND subreddit = :subreddit"
        params["subreddit"] = subreddit

    if start_date:
        query += " AND post_timestamp >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND post_timestamp <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY post_timestamp DESC"

    if limit:
        query += " LIMIT :limit"
        params["limit"] = limit

    df = execute_read_query(query, params=params, as_dataframe=True)
    return df if df is not None else pd.DataFrame()


def read_reddit_comments_for_posts(post_ids: List[str], limit_per_post: int = 10) -> pd.DataFrame:
    """Read top comments for specific Reddit posts."""
    if not post_ids:
        return pd.DataFrame()

    ## Create placeholders for IN clause
    placeholders = ','.join([f':post_id_{i}' for i in range(len(post_ids))])
    params = {f'post_id_{i}': post_id for i, post_id in enumerate(post_ids)}
    params['limit_per_post'] = limit_per_post

    query = f"""
        SELECT *
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY post_reddit_id ORDER BY score DESC) as rn
            FROM reddit_comments
            WHERE post_reddit_id IN ({placeholders})
        ) ranked_comments
        WHERE rn <= :limit_per_post
        ORDER BY post_reddit_id, score DESC
    """

    df = execute_read_query(query, params=params, as_dataframe=True)
    return df if df is not None else pd.DataFrame()


def store_reddit_analysis(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    subreddit: str,
    unique_posts: int,
    total_comments: int,
    top_posts_analyzed: int,
    thinking_process: str,
    response: str,
    metadata: Optional[Dict] = None,
) -> bool:
    """Store Reddit analysis results in the database."""
    query = """
        INSERT INTO reddit_analysis (
            start_date, end_date, subreddit, unique_posts, total_comments,
            top_posts_analyzed, thinking_process, response, metadata
        )
        VALUES (
            :start_date, :end_date, :subreddit, :unique_posts, :total_comments,
            :top_posts_analyzed, :thinking_process, :response, :metadata
        )
    """

    params = {
        "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
        "subreddit": subreddit,
        "unique_posts": unique_posts,
        "total_comments": total_comments,
        "top_posts_analyzed": top_posts_analyzed,
        "thinking_process": thinking_process,
        "response": response,
        "metadata": json.dumps(metadata) if metadata else None,
    }

    success = execute_write_query(query, params)
    if success:
        logging.info(f"Successfully stored Reddit analysis for {subreddit}")
    return success


def read_last_n_reddit_analyses(n: int = 10, subreddit: Optional[str] = None) -> pd.DataFrame:
    """Read the last N Reddit analyses from the database."""
    query = "SELECT * FROM reddit_analysis WHERE 1=1"
    params = {"limit": n}

    if subreddit:
        query += " AND subreddit = :subreddit"
        params["subreddit"] = subreddit

    query += " ORDER BY tstp DESC LIMIT :limit"

    df = execute_read_query(query, params=params, as_dataframe=True)
    return df if df is not None else pd.DataFrame()


def get_unposted_reddit_analyses(max_age_hours: int = 3, subreddit: Optional[str] = None) -> pd.DataFrame:
    """Get unposted Reddit analyses that are not too old."""
    query = """
        SELECT * FROM reddit_analysis
        WHERE posted_at IS NULL
        AND tstp > NOW() - INTERVAL '%s hours'
    """ % max_age_hours

    params = {}
    if subreddit:
        query += " AND subreddit = :subreddit"
        params["subreddit"] = subreddit

    query += " ORDER BY tstp ASC"

    df = execute_read_query(query, params=params, as_dataframe=True)
    return df if df is not None else pd.DataFrame()


def mark_analysis_as_posted(analysis_id: int) -> bool:
    """Mark a Reddit analysis as posted to X.com to avoid duplicates."""
    query = """
        UPDATE reddit_analysis
        SET posted_at = :timestamp
        WHERE id = :id
    """
    
    params = {
        "timestamp": datetime.now(),
        "id": analysis_id
    }

    success = execute_write_query(query, params)
    if success:
        logging.info(f"Marked Reddit analysis ID {analysis_id} as posted")
    return success


def get_last_posted_analysis_timestamp(subreddit: Optional[str] = None) -> Optional[datetime]:
    """Get the timestamp of the last analysis that was successfully posted."""
    query = """
        SELECT MAX(posted_at) as last_posted
        FROM reddit_analysis
        WHERE posted_at IS NOT NULL
    """
    
    params = {}
    if subreddit:
        query += " AND subreddit = :subreddit"
        params["subreddit"] = subreddit

    df = execute_read_query(query, params=params, as_dataframe=True)
    if df is not None and not df.empty and df.iloc[0]['last_posted'] is not None:
        return pd.to_datetime(df.iloc[0]['last_posted'])
    return None 