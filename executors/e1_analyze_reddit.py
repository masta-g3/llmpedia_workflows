#!/usr/bin/env python3

import sys, os
from dotenv import load_dotenv
import pandas as pd
from typing import Optional, List
from sqlalchemy import create_engine, text
from dataclasses import dataclass
import argparse
from datetime import datetime

load_dotenv()
PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
sys.path.append(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.reddit_db as reddit_db
import utils.vector_store as vs
from utils.reddit import format_reddit_content_for_analysis, format_multi_subreddit_content_for_analysis, LLM_SUBREDDITS

# Set up logging
logger = setup_logger(__name__, "e1_analyze_reddit.log")

@dataclass
class RedditAnalysisResult:
    """Container for Reddit analysis results."""
    min_date: pd.Timestamp
    max_date: pd.Timestamp
    subreddit: str
    unique_posts: int
    total_comments: int
    thinking_process: str
    response: str

def get_subreddits_by_priority(priority_filter: Optional[int] = None) -> List[str]:
    """Get list of subreddits based on priority filter."""
    if priority_filter is None:
        return list(LLM_SUBREDDITS.keys())
    
    return [
        name for name, config in LLM_SUBREDDITS.items()
        if config["priority"] <= priority_filter
    ]

def process_reddit_content(
    subreddit: str,
    start_time: Optional[str] = None, 
    end_time: Optional[str] = None
) -> Optional[RedditAnalysisResult]:
    """Process Reddit posts and comments and extract key insights.
    
    Modes:
    1. No parameters: Analyze last 24 hours (auto-calculate)
    2. start_time only: Analyze from start_time to now
    3. start_time + end_time: Analyze specific time window
    """
    
    # Calculate time range based on provided parameters
    if start_time is None and end_time is None:
        # Mode 1: Auto-calculate last 24 hours
        end_date = pd.Timestamp.now()
        start_date = end_date - pd.Timedelta(hours=24)
        logger.info(f"Auto-calculating: Processing Reddit content from r/{subreddit} for last 24 hours")
    elif start_time is not None and end_time is None:
        # Mode 2: Custom start date to now
        start_date = pd.Timestamp(start_time)
        end_date = pd.Timestamp.now()
        logger.info(f"Processing Reddit content from r/{subreddit} from {start_time} to now")
    elif start_time is not None and end_time is not None:
        # Mode 3: Custom start and end dates
        start_date = pd.Timestamp(start_time)
        end_date = pd.Timestamp(end_time)
        logger.info(f"Processing Reddit content from r/{subreddit} from {start_time} to {end_time}")
    else:
        # end_time without start_time doesn't make sense
        logger.error("Cannot specify end_time without start_time")
        return None
    
    # Get posts
    posts_df = reddit_db.read_reddit_posts(
        subreddit=subreddit,
        start_date=start_date.strftime("%Y-%m-%d %H:%M:%S"),
        end_date=end_date.strftime("%Y-%m-%d %H:%M:%S")
    )
    
    if posts_df.empty:
        logger.warning(f"No posts found for r/{subreddit} in the specified time range")
        return None
        
    # Remove duplicates and process timestamps
    posts_df.drop_duplicates(subset="title", keep="first", inplace=True)
    posts_df["post_timestamp"] = pd.to_datetime(posts_df["post_timestamp"])
    
    # Get comments for these posts
    post_ids = posts_df["reddit_id"].tolist()
    comments_df = reddit_db.read_reddit_comments_for_posts(post_ids, limit_per_post=5)
    
    # Get key metrics
    min_date = posts_df["post_timestamp"].min()
    max_date = posts_df["post_timestamp"].max()
    unique_posts = posts_df["title"].nunique()
    total_comments = len(comments_df)
    
    # Get previous analyses and format as diary entries
    previous_analyses = reddit_db.read_last_n_reddit_analyses(10, subreddit=subreddit)
    previous_entries = ""
    if not previous_analyses.empty:
        entries = []
        for _, row in previous_analyses.iterrows():
            timestamp = pd.to_datetime(row['tstp']).strftime("%Y-%m-%d %H:%M")
            entries.append(f"[{timestamp}] {row['response']}")
        previous_entries = "\n".join(entries)
    
    # Format and analyze Reddit content
    reddit_content = format_reddit_content_for_analysis(posts_df, comments_df)
    response = vs.analyze_reddit_patterns(
        reddit_content=reddit_content,
        subreddit=subreddit,
        previous_entries=previous_entries,
        start_date=min_date.strftime("%Y-%m-%d %H:%M:%S"),
        end_date=max_date.strftime("%Y-%m-%d %H:%M:%S"),
        model="gemini/gemini-2.5-pro-preview-06-05"
    )
    thinking_process = "~INTERNAL THINKING~"
    
    logger.info(f"Found {unique_posts} unique posts and {total_comments} comments from r/{subreddit} between {min_date} and {max_date}")
    logger.info("Completed Reddit pattern analysis")
    
    return RedditAnalysisResult(
        min_date=min_date,
        max_date=max_date,
        subreddit=subreddit,
        unique_posts=unique_posts,
        total_comments=total_comments,
        thinking_process=thinking_process,
        response=response
    )

def process_cross_subreddit_content(
    subreddits: List[str],
    start_time: Optional[str] = None, 
    end_time: Optional[str] = None
) -> Optional[RedditAnalysisResult]:
    """Process Reddit content from multiple subreddits for cross-community analysis."""
    
    # Calculate time range based on provided parameters
    if start_time is None and end_time is None:
        # Mode 1: Auto-calculate last 24 hours
        end_date = pd.Timestamp.now()
        start_date = end_date - pd.Timedelta(hours=24)
        logger.info(f"Auto-calculating: Processing cross-subreddit content for last 24 hours")
    elif start_time is not None and end_time is None:
        # Mode 2: Custom start date to now
        start_date = pd.Timestamp(start_time)
        end_date = pd.Timestamp.now()
        logger.info(f"Processing cross-subreddit content from {start_time} to now")
    elif start_time is not None and end_time is not None:
        # Mode 3: Custom start and end dates
        start_date = pd.Timestamp(start_time)
        end_date = pd.Timestamp(end_time)
        logger.info(f"Processing cross-subreddit content from {start_time} to {end_time}")
    else:
        # end_time without start_time doesn't make sense
        logger.error("Cannot specify end_time without start_time")
        return None

    logger.info(f"Processing cross-subreddit analysis for: {', '.join([f'r/{s}' for s in subreddits])}")
    
    # Collect posts from all subreddits
    all_posts = []
    all_comments = []
    
    for subreddit in subreddits:
        # Get posts
        posts_df = reddit_db.read_reddit_posts(
            subreddit=subreddit,
            start_date=start_date.strftime("%Y-%m-%d %H:%M:%S"),
            end_date=end_date.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        if not posts_df.empty:
            posts_df.drop_duplicates(subset="title", keep="first", inplace=True)
            posts_df["post_timestamp"] = pd.to_datetime(posts_df["post_timestamp"])
            all_posts.append(posts_df)
            
            # Get comments for these posts
            post_ids = posts_df["reddit_id"].tolist()
            comments_df = reddit_db.read_reddit_comments_for_posts(post_ids, limit_per_post=3)
            if not comments_df.empty:
                all_comments.append(comments_df)
    
    if not all_posts:
        logger.warning(f"No posts found for any subreddit in the specified time range")
        return None
    
    # Combine all posts and comments
    combined_posts_df = pd.concat(all_posts, ignore_index=True)
    combined_comments_df = pd.concat(all_comments, ignore_index=True) if all_comments else pd.DataFrame()
    
    # Get key metrics
    min_date = combined_posts_df["post_timestamp"].min()
    max_date = combined_posts_df["post_timestamp"].max()
    unique_posts = combined_posts_df["title"].nunique()
    total_comments = len(combined_comments_df)
    
    # Get previous cross-subreddit analyses (look for subreddit="multi")
    previous_analyses = reddit_db.read_last_n_reddit_analyses(10, subreddit="multi")
    previous_entries = ""
    if not previous_analyses.empty:
        entries = []
        for _, row in previous_analyses.iterrows():
            timestamp = pd.to_datetime(row['tstp']).strftime("%Y-%m-%d %H:%M")
            entries.append(f"[{timestamp}] {row['response']}")
        previous_entries = "\n".join(entries)
    
    # Format and analyze multi-subreddit content
    multi_subreddit_content = format_multi_subreddit_content_for_analysis(combined_posts_df, combined_comments_df)
    response = vs.analyze_cross_subreddit_patterns(
        multi_subreddit_content=multi_subreddit_content,
        previous_entries=previous_entries,
        start_date=min_date.strftime("%Y-%m-%d %H:%M:%S"),
        end_date=max_date.strftime("%Y-%m-%d %H:%M:%S"),
        model="claude-3-7-sonnet-20250219"
    )
    thinking_process = "~CROSS-SUBREDDIT THINKING~"
    
    logger.info(f"Found {unique_posts} unique posts and {total_comments} comments across {len(subreddits)} subreddits between {min_date} and {max_date}")
    logger.info("Completed cross-subreddit pattern analysis")
    
    return RedditAnalysisResult(
        min_date=min_date,
        max_date=max_date,
        subreddit="multi",  # Special identifier for cross-subreddit analysis
        unique_posts=unique_posts,
        total_comments=total_comments,
        thinking_process=thinking_process,
        response=response
    )

def main():
    """Load Reddit content and analyze community patterns."""
    parser = argparse.ArgumentParser(description="Analyze Reddit content from a specific time period")
    parser.add_argument("--start-time", type=str, help="Start time in YYYY-MM-DD HH:MM:SS format")
    parser.add_argument("--end-time", type=str, help="End time in YYYY-MM-DD HH:MM:SS format (optional)")
    parser.add_argument("--cross-subreddit", action="store_true", help="Perform cross-subreddit analysis (must be used with --priority)")
    
    # Subreddit selection - mutually exclusive options
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--subreddit", type=str, help="Specific subreddit to analyze (e.g., LocalLLaMA)")
    group.add_argument("--priority", type=int, choices=[1, 2, 3], help="Analyze all subreddits of specified priority tier (1=high, 2=medium, 3=low)")
    
    args = parser.parse_args()

    # Validate cross-subreddit flag
    if args.cross_subreddit and not args.priority:
        logger.error("--cross-subreddit flag requires --priority to be specified")
        sys.exit(1)

    # Determine which subreddits to process and analysis mode
    if args.subreddit:
        subreddits_to_analyze = [args.subreddit]
        analysis_mode = "single"
        logger.info(f"Starting Reddit analysis for specific subreddit: r/{args.subreddit}")
    elif args.priority:
        subreddits_to_analyze = get_subreddits_by_priority(args.priority)
        priority_names = {1: "high", 2: "medium", 3: "low"}
        
        if args.cross_subreddit:
            analysis_mode = "cross_subreddit"
            logger.info(f"Starting cross-subreddit analysis for priority {args.priority} ({priority_names[args.priority]}) communities: {subreddits_to_analyze}")
        else:
            analysis_mode = "individual"
            logger.info(f"Starting individual Reddit analysis for priority {args.priority} ({priority_names[args.priority]}) subreddits: {subreddits_to_analyze}")
    else:
        # Default behavior: analyze LocalLLaMA (maintain backward compatibility)
        subreddits_to_analyze = ["LocalLLaMA"]
        analysis_mode = "single"
        logger.info("No subreddit or priority specified, defaulting to r/LocalLLaMA")
    
    try:
        if analysis_mode == "cross_subreddit":
            # Cross-subreddit analysis: analyze all subreddits together
            result = process_cross_subreddit_content(
                subreddits=subreddits_to_analyze,
                start_time=args.start_time,
                end_time=args.end_time
            )
            
            if not result:
                logger.error("Failed to process cross-subreddit content")
                sys.exit(1)
                
            # Store results with metadata about analyzed subreddits
            metadata = {"subreddits_analyzed": subreddits_to_analyze}
            reddit_db.store_reddit_analysis(
                start_date=result.min_date,
                end_date=result.max_date,
                subreddit=result.subreddit,  # "multi"
                unique_posts=result.unique_posts,
                total_comments=result.total_comments,
                top_posts_analyzed=result.unique_posts,
                thinking_process=result.thinking_process,
                response=result.response,
                metadata=metadata
            )
            logger.info(f"Cross-subreddit analysis completed successfully for {len(subreddits_to_analyze)} communities")
            
        else:
            # Individual subreddit analysis: process each subreddit separately
            total_analyses = 0
            successful_analyses = 0
            
            for subreddit in subreddits_to_analyze:
                logger.info(f"Processing r/{subreddit}...")
                total_analyses += 1
                
                # Process Reddit content from specified time range
                result = process_reddit_content(
                    subreddit=subreddit,
                    start_time=args.start_time,
                    end_time=args.end_time
                )
                
                if not result:
                    logger.warning(f"Failed to process Reddit content for r/{subreddit} - skipping")
                    continue
                    
                # Store results
                reddit_db.store_reddit_analysis(
                    start_date=result.min_date,
                    end_date=result.max_date,
                    subreddit=result.subreddit,
                    unique_posts=result.unique_posts,
                    total_comments=result.total_comments,
                    top_posts_analyzed=result.unique_posts,  # For now, same as unique_posts
                    thinking_process=result.thinking_process,
                    response=result.response
                )
                successful_analyses += 1
                logger.info(f"Reddit analysis completed successfully for r/{subreddit}")
            
            logger.info(f"Analysis complete: {successful_analyses}/{total_analyses} subreddits processed successfully")
            
            if successful_analyses == 0:
                logger.error("No subreddits were successfully analyzed")
                sys.exit(1)
            
    except Exception as e:
        logger.error(f"An error occurred in the main process: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 