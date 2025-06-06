#!/usr/bin/env python3

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List, Dict
import time
import tempfile
from dotenv import load_dotenv

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

from utils.logging_utils import setup_logger
import utils.db.paper_db as paper_db
from utils.db.logging_db import log_workflow_run
import utils.app_utils as au
import utils.tweet as tweet
from utils.tweet import Tweet, TweetThread, boldify
from utils.plots import generate_daily_papers_chart

logger = setup_logger(__name__, "a1_daily_update.log")


@dataclass
class DailyStats:
    """Container for daily paper statistics."""
    total_papers: int
    topic_distribution: Dict[str, int]
    top_cited_authors: List[str]
    trending_topics: List[str]
    time_window: timedelta
    top_cited_papers: List[Dict[str, str]]
    total_papers_in_archive: int


def analyze_papers(papers_df: pd.DataFrame) -> DailyStats:
    """Analyze papers and generate interesting statistics."""
    ## Get total number of papers in archive
    count_df = paper_db.load_arxiv(select_cols=["COUNT(*) as count"])
    total_papers_in_archive = count_df['count'].iloc[0] if not count_df.empty else 0

    if papers_df.empty:
        return DailyStats(
            total_papers=0,
            topic_distribution={},
            top_cited_authors=[],
            trending_topics=[],
            time_window=timedelta(hours=24),
            top_cited_papers=[],
            total_papers_in_archive=total_papers_in_archive
        )
    
    ## Calculate basic stats
    total_papers = len(papers_df)
    
    ## Get topic distribution
    topic_dist = papers_df['topic'].value_counts().to_dict()
    
    ## Get top authors (split author strings and count unique)
    all_authors = []
    for authors in papers_df['authors']:
        all_authors.extend([a.strip() for a in authors.split(',')])
    top_authors = pd.Series(all_authors).value_counts().head(3).index.tolist()
    
    ## Find trending topics by looking at recent frequency
    trending = papers_df['topic'].value_counts().head(3).index.tolist()
    
    ## Get citation information for papers
    citations_df = paper_db.load_citations()
    papers_df = papers_df.merge(citations_df[['citation_count']], left_on='arxiv_code', right_index=True, how='left')
    papers_df['citation_count'] = papers_df['citation_count'].fillna(0)
    
    ## Get top cited papers with more than 10 citations
    top_cited = papers_df[papers_df['citation_count'] >= 10].nlargest(2, 'citation_count')
    top_cited_papers = [
        {'title': row['title'], 'citations': int(row['citation_count'])}
        for _, row in top_cited.iterrows()
    ]
    
    return DailyStats(
        total_papers=total_papers,
        topic_distribution=topic_dist,
        top_cited_authors=top_authors,
        trending_topics=trending,
        time_window=timedelta(hours=24),
        top_cited_papers=top_cited_papers,
        total_papers_in_archive=total_papers_in_archive
    )

def generate_tweet_content(stats: DailyStats) -> str:
    """Generate engaging tweet content from paper statistics."""
    if stats.total_papers == 0:
        return f"LLMpedia update: No new papers added in the last 24 hours. We now have {stats.total_papers_in_archive:,} papers in the archive. Stay tuned for more updates! #AI #LLM"
    
    ## Format topic distribution
    top_topics = sorted(
        stats.topic_distribution.items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:3]
    
    ## Create bullet points for topics using arrows
    topics_list = "\n".join([f"  → {topic} ({count})" for topic, count in top_topics])
    
    ## Create tweet content with emoji and better spacing
    tweet = boldify("📚 LLMpedia Nightly Digest: ")
    tweet += f"{stats.total_papers} new papers added in the last 24h, bringing the archive to {stats.total_papers_in_archive:,} papers.\n"
    tweet += boldify(f"⭐️ Top research areas:")
    tweet += f"\n{topics_list}"
    
    ## Add top cited papers if any, with better formatting
    if stats.top_cited_papers:
        tweet += "\n\n✨ Highly cited papers:"
        for paper in stats.top_cited_papers:
            tweet += f"\n⭐ {paper['title']}\n   {paper['citations']} citations"
    
    return tweet

def create_daily_update_tweet(stats: DailyStats, image_path: Optional[str] = None) -> TweetThread:
    """Create a TweetThread object for the daily update, optionally attaching an image."""
    content = generate_tweet_content(stats)
    
    # Create metadata with additional stats
    metadata = {
        "total_papers": stats.total_papers,
        "total_papers_in_archive": stats.total_papers_in_archive,
        "top_topics": stats.trending_topics,
        "time_window_hours": 24,
        "generated_at": datetime.now().isoformat()
    }
    
    # Create a single tweet object
    tweet_obj = Tweet(
        content=content,
        images=[image_path] if image_path else None,
        position=0
    )

    # Create a tweet thread containing the single tweet
    return TweetThread(
        tweets=[tweet_obj],
        tweet_type="daily_update",
        metadata=metadata,
        arxiv_code=None  # Not paper-specific
    )

def main():
    """Generate and send daily update about new papers added to LLMpedia."""
    # time.sleep(60 * 60 * 1.33)  # Sleep for 1.33 hours
    logger.info("Starting daily update process")
    image_temp_file = None
    chart_image_path = None
    
    try:
        ## Get papers from last 24 hours for the main stats
        cutoff_time_24h = datetime.now() - timedelta(hours=24)
        papers_df_24h = paper_db.get_papers_since(cutoff_time_24h)
        logger.info(f"Found {len(papers_df_24h)} papers in the last 24 hours")

        ## Skip if fewer than 4 papers in the last 24h
        if len(papers_df_24h) < 4:
            logger.info("Fewer than 4 papers found in last 24h, skipping daily update")
            log_workflow_run('Daily Update', 'executors/a1_daily_update.py', 'skipped', 'Too few papers')
            return 2
        
        ## Analyze 24h papers.
        stats = analyze_papers(papers_df_24h)
        logger.info(f"Analyzed papers: {stats}")

        ## --- Generate 14-day chart ---
        ## Fetch papers from the last 14 days
        cutoff_time_14d = datetime.now() - timedelta(days=14)
        papers_df_14d = paper_db.get_papers_since(cutoff_time_14d)
        logger.info(f"Found {len(papers_df_14d)} papers in the last 14 days for chart generation")

        if not papers_df_14d.empty:
            ## Create rolling 24-hour periods for the last 14 days
            now = datetime.now()
            daily_counts = []
            period_labels = []
            
            for day_offset in range(13, -1, -1):  # From 13 days ago to today
                period_start = now - timedelta(hours=24 * (day_offset + 1))
                period_end = now - timedelta(hours=24 * day_offset)
                
                # Count papers in this 24-hour period
                period_papers = papers_df_14d[
                    (pd.to_datetime(papers_df_14d['tstp']) >= period_start) &
                    (pd.to_datetime(papers_df_14d['tstp']) < period_end)
                ]
                
                daily_counts.append(len(period_papers))
                period_labels.append(period_end.date())  # Use end date for labeling
            
            # Convert to pandas Series for compatibility with chart function
            daily_counts = pd.Series(daily_counts, index=period_labels)

            ## Generate chart
            image_temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            chart_image_path = image_temp_file.name
            generate_daily_papers_chart(daily_counts, chart_image_path)
            logger.info(f"Generated 14-day paper count chart: {chart_image_path}")
        else:
            logger.warning("No papers found in the last 14 days, skipping chart generation.")

        ## Create tweet thread (passing potential image path)
        tweet_thread = create_daily_update_tweet(stats, image_path=chart_image_path)
        logger.info(f"Generated tweet content: {tweet_thread.tweets[0].content}")
        if chart_image_path:
            logger.info(f"Tweet will include image: {chart_image_path}")
        
        ## Try sending tweet with one retry.
        for attempt in range(2):
            tweet_success = tweet.send_tweet2(
                tweet_content=tweet_thread,
                logger=logger, 
                verify=True,
                headless=True
            )
            if tweet_success:
                break
            elif attempt == 0:
                logger.warning("First tweet attempt failed, retrying after 30 seconds...")
                time.sleep(30)
        
        if tweet_success:
            logger.info("Successfully sent daily update tweet")
            log_workflow_run('Daily Update', 'executors/a1_daily_update.py', 'success')
            return 0
        else:
            logger.error("Failed to send daily update tweet")
            log_workflow_run('Daily Update', 'executors/a1_daily_update.py', 'error', 'Failed to send tweet after retries')
            return 1
        
    except Exception as e:
        logger.error(f"Error in daily update process: {str(e)}")
        log_workflow_run('Daily Update', 'executors/a1_daily_update.py', 'error', str(e))
        raise
    finally:
        ## Clean up temporary image file if it was created
        if image_temp_file:
            try:
                os.remove(chart_image_path)
                logger.info(f"Removed temporary chart image: {chart_image_path}")
            except OSError as e:
                logger.error(f"Error removing temporary file {chart_image_path}: {e}")


if __name__ == "__main__":
    sys.exit(main()) 