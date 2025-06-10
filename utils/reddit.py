"""Reddit collection utilities for LLMpedia."""

import os
import sys
import time
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional, Iterator
import requests

from utils.vector_store import assess_llm_relevance
from .tweet import setup_browser  # Reuse browser setup from tweet.py
from .logging_utils import get_console_logger

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
sys.path.append(PROJECT_PATH)

## Reddit API credentials (optional - fallback to scraping if not available)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "LLMpedia:v1.0.0 (by /u/llmpedia)")

## Subreddit configuration following the plan
LLM_SUBREDDITS = {
    ## Tier 1 - Primary LLM Communities (High Priority)
    "LocalLLaMA": {"priority": 1, "members": "483k", "focus": "Local LLM deployment, Llama models, hardware optimization"},
    "ChatGPT": {"priority": 1, "members": "10.6M", "focus": "OpenAI ChatGPT discussions, use cases, troubleshooting"},
    "OpenAI": {"priority": 1, "members": "~2M", "focus": "OpenAI company news, GPT models, API discussions"},
    "LLMDevs": {"priority": 1, "members": "89k", "focus": "LLM development, fine-tuning, technical implementation"},
    "ollama": {"priority": 1, "members": "71k", "focus": "Ollama local LLM runtime, deployment tutorials"},
    
    ## Tier 2 - Model-Specific Communities (Medium Priority)
    "Claude": {"priority": 2, "members": "~50k", "focus": "Anthropic Claude discussions and use cases"},
    "DeepSeek": {"priority": 2, "members": "62k", "focus": "DeepSeek model discussions, benchmarks"},
    "LocalLLM": {"priority": 2, "members": "70k", "focus": "General local LLM deployment and optimization"},
    "AI_Agents": {"priority": 2, "members": "151k", "focus": "LLM-powered agent development and applications"},
    
    ## Tier 3 - Specialized LLM Communities (Low Priority)
    "Chatbots": {"priority": 3, "members": "99k", "focus": "LLM-powered chatbot development"},
    "LanguageModels": {"priority": 3, "members": "~10k", "focus": "Academic LLM research discussions"},
    "OpenSourceAI": {"priority": 3, "members": "~25k", "focus": "Open-source LLM projects and releases"},
}


def get_reddit_api_headers() -> Dict[str, str]:
    """Get Reddit API headers with authentication if available."""
    headers = {
        "User-Agent": REDDIT_USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    ## If we have API credentials, get an access token
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        try:
            auth_response = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": REDDIT_USER_AGENT}
            )
            if auth_response.status_code == 200:
                token = auth_response.json().get("access_token")
                headers["Authorization"] = f"bearer {token}"
        except Exception as e:
            logging.warning(f"Failed to get Reddit API token, falling back to scraping: {e}")
    
    return headers


def collect_subreddit_posts_api(
    subreddit_name: str, 
    limit: int = 50, 
    time_filter: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> List[Dict]:
    """Collect Reddit posts using the API (preferred method)."""
    logger = logger or get_console_logger()
    logger.info(f"Collecting posts from r/{subreddit_name} using API")
    
    headers = get_reddit_api_headers()
    url = f"https://www.reddit.com/r/{subreddit_name}/hot.json"
    
    params = {
        "limit": min(limit, 100),  # Reddit API limit is 100
        "t": time_filter
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        posts = []
        for post_data in data.get("data", {}).get("children", []):
            post = post_data.get("data", {})
            
            ## Convert Reddit post to our format
            post_timestamp = datetime.fromtimestamp(post.get("created_utc", 0)) if post.get("created_utc") else None
            
            ## Apply date filtering if specified (more precise than Reddit's time_filter)
            if start_date and post_timestamp:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
                if post_timestamp < start_dt:
                    continue
            
            if end_date and post_timestamp:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
                if post_timestamp > end_dt:
                    continue
            
            post_dict = {
                "reddit_id": post.get("id", ""),
                "subreddit": post.get("subreddit", subreddit_name),
                "title": post.get("title", ""),
                "selftext": post.get("selftext", ""),
                "author": post.get("author", ""),
                "url": post.get("url", ""),
                "permalink": f"https://www.reddit.com{post.get('permalink', '')}",
                "post_timestamp": post_timestamp.strftime("%Y-%m-%d %H:%M:%S") if post_timestamp else None,
                "score": post.get("score", 0),
                "upvote_ratio": post.get("upvote_ratio", None),
                "num_comments": post.get("num_comments", 0),
                "is_self": post.get("is_self", False),
                "post_type": "text" if post.get("is_self") else "link",
                "flair_text": post.get("link_flair_text", ""),
                "metadata": {
                    "subreddit_subscribers": post.get("subreddit_subscribers"),
                    "locked": post.get("locked", False),
                    "stickied": post.get("stickied", False),
                    "over_18": post.get("over_18", False),
                }
            }
            posts.append(post_dict)
        
        logger.info(f"Successfully collected {len(posts)} posts from r/{subreddit_name} via API")
        return posts
        
    except Exception as e:
        logger.error(f"API collection failed for r/{subreddit_name}: {e}")
        return []


def collect_subreddit_posts_scraping(
    subreddit_name: str,
    limit: int = 50,
    time_filter: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> List[Dict]:
    """Collect Reddit posts using web scraping (fallback method)."""
    logger = logger or get_console_logger()
    logger.info(f"Collecting posts from r/{subreddit_name} using web scraping")
    
    ## Note: Date filtering with scraping is limited - relies on Reddit's time_filter
    if start_date or end_date:
        logger.warning("Precise date filtering not available with scraping - using Reddit's time_filter only")
    
    browser = setup_browser(logger, headless=True)  # Reuse from tweet.py
    posts = []
    
    try:
        ## Navigate to subreddit
        url = f"https://www.reddit.com/r/{subreddit_name}/hot/"
        browser.get(url)
        time.sleep(3)
        
        ## Add rate limiting
        time.sleep(random.uniform(2, 5))
        
        ## Extract posts using CSS selectors (simplified - would need more robust implementation)
        post_elements = browser.find_elements("css selector", "[data-testid='post-container']")
        
        for i, post_elem in enumerate(post_elements[:limit]):
            try:
                ## Extract basic post data (this is a simplified implementation)
                title_elem = post_elem.find_element("css selector", "h3")
                title = title_elem.text if title_elem else "No title"
                
                ## This would need more sophisticated scraping logic
                post_dict = {
                    "reddit_id": f"scraped_{i}",  # Placeholder - would extract real ID
                    "subreddit": subreddit_name,
                    "title": title,
                    "selftext": "",  # Would extract from post content
                    "author": "unknown",  # Would extract from post metadata
                    "url": "",
                    "permalink": "",
                    "post_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "score": 0,  # Would extract from score element
                    "upvote_ratio": None,
                    "num_comments": 0,  # Would extract from comments element
                    "is_self": True,
                    "post_type": "text",
                    "flair_text": "",
                    "metadata": {"collection_method": "scraping"}
                }
                posts.append(post_dict)
                
            except Exception as e:
                logger.warning(f"Failed to extract post {i}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Scraping failed for r/{subreddit_name}: {e}")
    finally:
        browser.quit()
    
    logger.info(f"Collected {len(posts)} posts from r/{subreddit_name} via scraping")
    return posts


def collect_subreddit_posts(
    subreddit_name: str,
    limit: int = 50,
    time_filter: str = "day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> List[Dict]:
    """Collect Reddit posts with API fallback to scraping."""
    logger = logger or get_console_logger()
    
    ## Try API first
    posts = collect_subreddit_posts_api(subreddit_name, limit, time_filter, start_date, end_date, logger)
    
    ## Fallback to scraping if API fails
    if not posts:
        logger.warning(f"API collection failed for r/{subreddit_name}, trying scraping")
        posts = collect_subreddit_posts_scraping(subreddit_name, limit, time_filter, start_date, end_date, logger)
    
    return posts


def collect_post_comments_api(
    post_id: str,
    subreddit_name: str,
    max_comments: int = 20,
    max_depth: int = 3,
    logger: Optional[logging.Logger] = None
) -> List[Dict]:
    """Collect comments for a specific post using the API."""
    logger = logger or get_console_logger()
    
    headers = get_reddit_api_headers()
    url = f"https://www.reddit.com/r/{subreddit_name}/comments/{post_id}.json"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        comments = []
        
        ## Reddit returns [post_data, comments_data]
        if len(data) >= 2:
            comments_data = data[1].get("data", {}).get("children", [])
            
            def extract_comments(comment_list, depth=0, parent_id=None):
                """Recursively extract comments with depth tracking."""
                comment_count = 0
                for comment_data in comment_list:
                    if comment_count >= max_comments or depth > max_depth:
                        break
                        
                    comment = comment_data.get("data", {})
                    if comment.get("body") and comment.get("body") != "[removed]":
                        comment_dict = {
                            "reddit_id": comment.get("id", ""),
                            "post_reddit_id": post_id,
                            "parent_id": parent_id,
                            "subreddit": subreddit_name,
                            "author": comment.get("author", ""),
                            "body": comment.get("body", ""),
                            "comment_timestamp": datetime.fromtimestamp(comment.get("created_utc", 0)).strftime("%Y-%m-%d %H:%M:%S") if comment.get("created_utc") else None,
                            "score": comment.get("score", 0),
                            "depth": depth,
                            "is_top_level": depth == 0,
                            "metadata": {
                                "is_submitter": comment.get("is_submitter", False),
                                "stickied": comment.get("stickied", False),
                                "locked": comment.get("locked", False),
                            }
                        }
                        comments.append(comment_dict)
                        comment_count += 1
                        
                        ## Recursively get replies
                        replies = comment.get("replies", {})
                        if isinstance(replies, dict) and replies.get("data", {}).get("children"):
                            extract_comments(
                                replies["data"]["children"], 
                                depth + 1, 
                                comment.get("id")
                            )
            
            extract_comments(comments_data)
        
        logger.info(f"Collected {len(comments)} comments for post {post_id}")
        return comments
        
    except Exception as e:
        logger.error(f"Failed to collect comments for post {post_id}: {e}")
        return []


def collect_llm_subreddit_data(
    subreddit_list: Optional[List[str]] = None,
    posts_per_subreddit: int = 50,
    comments_per_post: int = 10,
    priority_filter: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> Iterator[Dict]:
    """Collect LLM-related posts and their comments from subreddits in batches."""
    logger = logger or get_console_logger()
    
    ## Use default subreddit list if none provided
    if subreddit_list is None:
        subreddits_to_process = [
            name for name, config in LLM_SUBREDDITS.items()
            if priority_filter is None or config["priority"] <= priority_filter
        ]
    else:
        subreddits_to_process = subreddit_list
    
    ## Log date range if specified
    if start_date or end_date:
        date_info = f"from {start_date}" if start_date else ""
        date_info += f" to {end_date}" if end_date else " to now"
        logger.info(f"Processing {len(subreddits_to_process)} subreddits {date_info}: {subreddits_to_process}")
    else:
        logger.info(f"Processing {len(subreddits_to_process)} subreddits (last day): {subreddits_to_process}")
    
    for subreddit_name in subreddits_to_process:
        logger.info(f"Processing r/{subreddit_name}")
        
        ## Collect posts
        posts = collect_subreddit_posts(
            subreddit_name=subreddit_name,
            limit=posts_per_subreddit,
            time_filter="day",  # Keep as fallback for Reddit API
            start_date=start_date,
            end_date=end_date,
            logger=logger
        )
        
        ## Extract arxiv codes and filter for LLM-related posts (following tweet pattern)
        llm_related_posts = []
        
        for post in posts:
            if post.get("title") or post.get("selftext"):
                ## Combine title and content for analysis
                post_text = f"{post.get('title', '')} {post.get('selftext', '')}"
                
                try:
                    relevance_info = assess_llm_relevance(
                        tweet_text=post_text, 
                        model="gemini/gemini-2.0-flash"
                    )
                    post["arxiv_code"] = relevance_info.arxiv_code
                    
                    ## Only keep LLM-related posts (following tweet workflow pattern)
                    if relevance_info.is_llm_related:
                        llm_related_posts.append(post)
                        logger.info(f"Found LLM-related post: {post.get('title', '')[:50]}... (ID: {post.get('reddit_id')})")
                        if relevance_info.arxiv_code:
                            logger.info(f"  -> Contains arxiv code: {relevance_info.arxiv_code}")
                    else:
                        logger.debug(f"Filtered out non-LLM post: {post.get('reddit_id')}")
                        
                except Exception as e:
                    logger.warning(f"Failed to assess LLM relevance for post {post.get('reddit_id')}: {e}")
                    ## If assessment fails, err on the side of inclusion
                    post["arxiv_code"] = None
                    llm_related_posts.append(post)
        
        logger.info(f"Filtered {len(llm_related_posts)} LLM-related posts from {len(posts)} total posts")
        
        all_comments = []
        ## Collect comments for LLM-related posts only
        for post in llm_related_posts:
            if post.get("reddit_id"):
                comments = collect_post_comments_api(
                    post_id=post["reddit_id"],
                    subreddit_name=subreddit_name,
                    max_comments=comments_per_post,
                    max_depth=2,
                    logger=logger
                )
                all_comments.extend(comments)
        
        ## Yield batch data for this subreddit (only LLM-related posts)
        yield {
            "subreddit": subreddit_name,
            "posts": llm_related_posts,
            "comments": all_comments,
            "collection_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        ## Add delay between subreddits to be respectful
        time.sleep(random.uniform(1, 3))


def format_reddit_content_for_analysis(posts_df, comments_df) -> str:
    """Format Reddit posts and comments for LLM analysis following tweet pattern."""
    content_parts = []
    
    ## Group comments by post
    comments_by_post = comments_df.groupby("post_reddit_id") if not comments_df.empty else {}
    
    for _, post in posts_df.iterrows():
        post_str = f"POST: {post['title']}\n"
        if post.get('selftext') and post['selftext'].strip():
            post_str += f"Content: {post['selftext'][:500]}{'...' if len(post['selftext']) > 500 else ''}\n"
        post_str += f"Author: {post['author']} | Score: {post['score']} | Comments: {post['num_comments']}\n"
        post_str += f"Time: {post['post_timestamp']}\n"
        
        ## Add top comments if available
        if post['reddit_id'] in comments_by_post:
            post_comments = comments_by_post.get_group(post['reddit_id'])
            top_comments = post_comments.nlargest(3, 'score')  # Top 3 by score
            
            if not top_comments.empty:
                post_str += "\nTOP COMMENTS:\n"
                for _, comment in top_comments.iterrows():
                    comment_text = comment['body'][:200] + ('...' if len(comment['body']) > 200 else '')
                    post_str += f"- [{comment['author']}] {comment_text} (score: {comment['score']})\n"
        
        content_parts.append(post_str)
    
    return "\n---\n".join(content_parts)


def format_multi_subreddit_content_for_analysis(posts_df, comments_df) -> str:
    """Format posts and comments from multiple subreddits for cross-community analysis."""
    ## Group posts by subreddit
    posts_by_subreddit = posts_df.groupby("subreddit")
    comments_by_post = comments_df.groupby("post_reddit_id") if not comments_df.empty else {}
    
    subreddit_sections = []
    
    for subreddit, subreddit_posts in posts_by_subreddit:
        subreddit_content = [f"=== r/{subreddit} ==="]
        
        ## Get top posts by engagement (score + comment count)
        subreddit_posts = subreddit_posts.copy()
        subreddit_posts['engagement'] = subreddit_posts['score'] + subreddit_posts['num_comments']
        top_posts = subreddit_posts.nlargest(5, 'engagement')  # Top 5 most engaging posts per subreddit
        
        for _, post in top_posts.iterrows():
            post_str = f"POST: {post['title']}\n"
            if post.get('selftext') and post['selftext'].strip():
                post_str += f"Content: {post['selftext'][:300]}{'...' if len(post['selftext']) > 300 else ''}\n"
            post_str += f"Author: {post['author']} | Score: {post['score']} | Comments: {post['num_comments']}\n"
            
            ## Add top 2 comments for cross-community analysis
            if post['reddit_id'] in comments_by_post:
                post_comments = comments_by_post.get_group(post['reddit_id'])
                top_comments = post_comments.nlargest(2, 'score')
                
                if not top_comments.empty:
                    post_str += "TOP COMMENTS:\n"
                    for _, comment in top_comments.iterrows():
                        comment_text = comment['body'][:150] + ('...' if len(comment['body']) > 150 else '')
                        post_str += f"- [{comment['author']}] {comment_text} (score: {comment['score']})\n"
            
            subreddit_content.append(post_str)
        
        subreddit_sections.append("\n".join(subreddit_content))
    
    return "\n\n".join(subreddit_sections) 