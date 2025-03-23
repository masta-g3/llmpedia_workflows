#!/usr/bin/env python3

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import logging
import time
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

PROJECT_PATH = os.environ.get("PROJECT_PATH")
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.tweet_db as tweet_db
import utils.vector_store as vs
from utils.paper_utils import extract_tagged_content
from utils.app_utils import query_llmpedia_new
import utils.tweet as tweet

## Suppress SettingWithCopyWarning
import warnings
warnings.filterwarnings('ignore')

logger = setup_logger(__name__, "c1_tweet_reply.log")


@dataclass
class TweetReplyData:
    """Container for storing tweet reply information."""
    selected_tweet: str
    selected_tweet_id: str
    response_type: str
    response: str
    llmpedia_context: Optional[str] = None


def format_tweet_thread(df: pd.DataFrame) -> str:
    """Formats a DataFrame of tweets and responses into a readable thread format."""
    formatted_thread = []
    
    ## Sort by timestamp to maintain conversation flow
    df_sorted = df.sort_values('tstp')
    
    for _, row in df_sorted.iterrows():
        ## Format original tweet
        formatted_thread.append("<selected_tweet>")
        formatted_thread.append(row['selected_tweet'].strip())
        formatted_thread.append("</selected_tweet>")
        
        ## Format response 
        formatted_thread.append("<tweet_response>")
        formatted_thread.append(row['response'].strip())
        formatted_thread.append("</tweet_response>")
        formatted_thread.append("------------------")  ## Separator between tweet-response pairs
    
    return "\n".join(formatted_thread)


def get_recent_tweets(time_span_hours: int = 48, sample_size: int = 50) -> str:
    """Retrieves and formats recent tweets from the database."""
    logger.info(f"Fetching tweets from the last {time_span_hours} hours")
    
    tweets_df = tweet_db.read_tweets(
        start_date=pd.Timestamp.now() - pd.Timedelta(hours=time_span_hours), 
        end_date=pd.Timestamp.now()
    )
    
    if tweets_df.empty:
        logger.warning("No tweets found in the specified time period")
        return ""
    
    ## Process tweets dataframe
    tweets_df.drop_duplicates(subset="text", keep="first", inplace=True)
    tweets_df["tstp"] = pd.to_datetime(tweets_df["tstp"], unit="s")
    tweets_df["date"] = pd.to_datetime(tweets_df["tstp"].dt.date)
    tweets_df["date_hour"] = tweets_df["tstp"].dt.floor('H')
    
    ## Sample tweets if there are more than the sample size
    if len(tweets_df) > sample_size:
        tweets_df = tweets_df.sample(n=sample_size).reset_index(drop=True)
    
    start_date = tweets_df["tstp"].min().strftime("%Y-%m-%d")
    end_date = tweets_df["tstp"].max().strftime("%Y-%m-%d")
    logger.info(f"Tweets range from {start_date} to {end_date}")
    logger.info(f"Found {len(tweets_df)} tweets after processing")
    
    ## Format tweets as string
    tweets_raw = []
    for _, row in tweets_df.iterrows():
        timestamp = row["tstp"].strftime("%Y-%m-%d %H:%M")
        username = row["username"]
        text = row["text"]
        tweet_id = row["id"]
        tweets_raw.append(f"<tweet>\n<id>{tweet_id}</id>\n<tstp>{timestamp}</tstp>\n<author>{username}</author>\n<text>\n{text}\n</text>\n</tweet>")
    
    return "\n".join(tweets_raw)


def get_recent_discussions(days: int = 2, n: int = 5) -> str:
    """Retrieves and formats recent tweet analyses from the database."""
    logger.info(f"Fetching the last {n} tweet analyses from the past {days} days")
    
    discussion_df = tweet_db.read_last_n_tweet_analyses(n=n)
    discussion_df = discussion_df[discussion_df["tstp"] > pd.Timestamp.now() - pd.Timedelta(days=days)]
    
    if discussion_df.empty:
        logger.warning("No recent discussions found")
        return ""
    
    ## Format discussions with timestamps
    discussions = []
    for _, row in discussion_df.iterrows():
        timestamp = row["tstp"].strftime("%Y-%m-%d %H:%M")
        discussions.append(f"<discussion_summary>")
        discussions.append(f"<timestamp>{timestamp}</timestamp>")
        discussions.append(f"<summary>")
        discussions.append(row["response"].strip())
        discussions.append(f"</summary>")
        discussions.append(f"</discussion_summary>")
    
    logger.info(f"Found {len(discussion_df)} recent discussions")
    return "\n".join(discussions)


def get_previous_replies(days: int = 10, limit: int = 30) -> str:
    """Retrieves and formats previous tweet replies as a thread."""
    logger.info(f"Fetching tweet replies from the past {days} days")
    
    threads_df = tweet_db.read_tweet_replies(start_date=pd.Timestamp.now() - pd.Timedelta(days=days))
    
    if threads_df.empty:
        logger.warning("No previous replies found")
        return ""
    
    threads_df.sort_values(by="tstp", ascending=False, inplace=True)
    previous_posts = format_tweet_thread(threads_df.head(limit))
    
    logger.info(f"Found {min(len(threads_df), limit)} previous replies")
    return previous_posts


def select_tweet_to_reply() -> Dict[str, str]:
    """Selects a tweet to reply to from the recent tweet pool."""
    logger.info("Selecting a tweet to reply to")
    
    ## Get recent tweets and discussions
    tweets_str = get_recent_tweets()
    recent_discussion_str = get_recent_discussions()
    
    if not tweets_str:
        logger.error("No tweets available to select from")
        return {}
    
    ## Select a tweet to reply to
    selected_tweet = vs.select_tweet_reply(tweets_str, recent_discussion_str)
    selected_tweet_dict = extract_tagged_content(
        selected_tweet, ["selected_post", "selected_post_id", "response_type"]
    )
    
    if not selected_tweet_dict or "selected_post" not in selected_tweet_dict:
        logger.error("Failed to select a tweet to reply to")
        return {}
    
    logger.info(f"Selected tweet: {selected_tweet_dict['selected_post']}...")
    logger.info(f"Response type: {selected_tweet_dict.get('response_type', 'unknown')}")
    
    return selected_tweet_dict


def find_related_content(selected_tweet: str) -> str:
    """Finds relevant content from LLMpedia for the selected tweet."""
    logger.info("Finding related content for the selected tweet")
    
    search_query = """I am trying to find LLM papers from 2024 onwards that could help me build an insightful reply to this tweet:

<selected_tweet>
{selected_tweet}
</selected_tweet>
"""
    
    res = query_llmpedia_new(
        user_question=search_query.format(selected_tweet=selected_tweet),
        show_only_sources=False,
        max_sources=25,
    )
    
    if not res:
        logger.warning("No related content found")
        return ""
    
    llmpedia_analysis = res[0]
    logger.info(f"Found related content: {llmpedia_analysis[:100]}...")
    
    return llmpedia_analysis


def generate_reply(selected_tweet_dict: Dict[str, str], llmpedia_analysis: str, previous_posts: str, recent_discussion_str: str) -> Tuple[str, str]:
    """Generates an appropriate reply based on the tweet's response type."""
    logger.info(f"Generating reply for response type: {selected_tweet_dict.get('response_type', 'unknown')}")
    
    selected_post = selected_tweet_dict.get("selected_post", "")
    response_type = selected_tweet_dict.get("response_type", "a")  ## Default to academic
    
    ## For response type 'b' (funny response)
    if response_type == "b":
        logger.info("Generating funny reply")
        funny_reply = vs.write_tweet_reply_funny(
            selected_post=selected_post,
            summary_of_recent_discussions=recent_discussion_str,
            previous_posts=previous_posts,
            model="claude-3-7-sonnet-20250219",
            temperature=1,
        )
        funny_reply_dict = extract_tagged_content(funny_reply, ["post_response"])
        if not funny_reply_dict or "post_response" not in funny_reply_dict:
            logger.error("Failed to generate funny reply")
            return "", "funny"
        return funny_reply_dict["post_response"], "funny"
    
    ## For response type 'c' (common-sense response)
    elif response_type == "c":
        logger.info("Generating commonsense reply")
        commonsense_reply = vs.write_tweet_reply_commonsense(
            selected_post=selected_post,
            summary_of_recent_discussions=recent_discussion_str,
            previous_posts=previous_posts,
            model="claude-3-7-sonnet-20250219",
            temperature=1,
        )
        commonsense_reply_dict = extract_tagged_content(commonsense_reply, ["post_response"])
        if not commonsense_reply_dict or "post_response" not in commonsense_reply_dict:
            logger.error("Failed to generate commonsense reply")
            return "", "commonsense"
        return commonsense_reply_dict["post_response"], "commonsense"
    
    ## For response type 'a' (academic response) or default
    else:
        logger.info("Generating academic reply")
        academic_reply = vs.write_tweet_reply_academic(
            selected_post=selected_post,
            context=llmpedia_analysis,
            summary_of_recent_discussions=recent_discussion_str,
            previous_posts=previous_posts,
            model="claude-3-7-sonnet-20250219",
            temperature=1,
        )
        academic_reply_dict = extract_tagged_content(academic_reply, ["post_response"])
        if not academic_reply_dict or "post_response" not in academic_reply_dict:
            logger.error("Failed to generate academic reply")
            return "", "academic"
        return academic_reply_dict["post_response"], "academic"


def store_reply(selected_tweet: str, response: str, response_type: str) -> bool:
    """Stores the generated tweet reply in the database."""
    logger.info(f"Storing {response_type} reply in the database")
    
    meta_data = {
        "type": response_type,
        "generated_at": datetime.now().isoformat()
    }
    
    success = tweet_db.store_tweet_reply(selected_tweet, response, meta_data)
    
    if success:
        logger.info("Successfully stored reply in the database")
    else:
        logger.error("Failed to store reply in the database")
    
    return success


def main():
    """Executes the tweet reply workflow: select tweet, generate reply, store it."""
    logger.info("Starting tweet reply process")
    
    try:
        ## Get previous replies for context
        previous_posts = get_previous_replies()
        recent_discussion_str = get_recent_discussions()
        
        ## Select a tweet to reply to
        selected_tweet_dict = select_tweet_to_reply()
        if not selected_tweet_dict:
            logger.error("No tweet selected, exiting")
            return 1
        
        ## Find related content for academic replies
        llmpedia_analysis = ""
        if selected_tweet_dict.get("response_type", "a") == "a":
            llmpedia_analysis = find_related_content(selected_tweet_dict["selected_post"])
        
        ## Generate reply
        response, response_type = generate_reply(
            selected_tweet_dict, 
            llmpedia_analysis, 
            previous_posts, 
            recent_discussion_str
        )
        
        if not response:
            logger.error("Failed to generate reply, exiting")
            return 1
        
        logger.info(f"Generated {response_type} reply: {response}...")
        
        ## Store reply in the database
        success = store_reply(
            selected_tweet_dict["selected_post"], 
            response, 
            response_type
        )
        
        if not success:
            logger.error("Failed to store reply, exiting")
            return 1
        
        logger.info("Tweet reply process completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error in tweet reply process: {str(e)}")
        raise

if __name__ == "__main__":
    sys.exit(main()) 