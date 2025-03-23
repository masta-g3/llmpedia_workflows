#!/usr/bin/env python3

import datetime
import os, sys, re
import time
import random
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import base64
from dataclasses import dataclass
from typing import Optional, Tuple, List
import logging

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
load_dotenv(os.path.join(PROJECT_PATH, '.env'))
sys.path.append(PROJECT_PATH)

DATA_PATH = os.path.join(PROJECT_PATH, "data")
IMG_PATH = os.path.join(DATA_PATH, "arxiv_art")
PAGE_PATH = os.path.join(DATA_PATH, "arxiv_first_page")

from utils.logging_utils import setup_logger
import utils.vector_store as vs
import utils.paper_utils as pu
import utils.notifications as em
import utils.db.db_utils as db_utils
import utils.db.paper_db as paper_db
import utils.db.tweet_db as tweet_db
from utils.tweet import bold
import utils.tweet as tweet
import utils.app_utils as au

logger = setup_logger(__name__, "z1_generate_tweet.log")


@dataclass
class TweetContent:
    """Container for generated tweet content and metadata."""

    content: str
    post_content: str
    tweet_type: str
    arxiv_code: str
    publish_date: str
    selected_image: Optional[str] = None
    selected_table: Optional[str] = None


@dataclass
class TweetImages:
    """Container for tweet image paths."""

    tweet_image: Optional[str] = None  # Art image
    tweet_page: Optional[str] = None  # First page or selected figure
    analyzed_image: Optional[str] = None  # Additional analyzed figure


## New function to fetch candidate papers from S3, excluding those already reviewed.
def fetch_candidate_papers(logger: logging.Logger) -> List[str]:
    """Fetch candidates from S3 excluding already reviewed papers."""
    ## Get list of papers not yet reviewed.
    arxiv_codes = pu.list_s3_files("arxiv-art", strip_extension=True)
    done_codes = db_utils.get_arxiv_id_list("tweet_reviews")
    candidates = list(set(arxiv_codes) - set(done_codes))
    # Limit to the most recent 250 papers.
    candidates = sorted(candidates)[-250:]
    logger.info(f"Found {len(candidates)} recent papers to consider")
    return candidates


## New function to choose the most interesting paper from candidates.
def choose_interesting_paper(candidates: List[str], logger: logging.Logger) -> str:
    """Select the most interesting candidate paper based on citations."""
    citations_df = paper_db.load_citations()
    citations_df = citations_df[citations_df.index.isin(candidates)]
    citations_df["citation_count"] = citations_df["citation_count"].fillna(1) + 1
    citations_df["weight"] = (
        citations_df["citation_count"] / citations_df["citation_count"].sum()
    )
    citations_df["weight"] = citations_df["weight"] ** 0.5
    citations_df["weight"] = citations_df["weight"] / citations_df["weight"].sum()

    candidate_arxiv_codes = np.random.choice(
        citations_df.index,
        size=25,
        replace=False,
        p=citations_df["weight"] / citations_df["weight"].sum(),
    )
    logger.info(
        f"Selected {len(candidate_arxiv_codes)} candidate papers based on citations"
    )

    candidate_abstracts = paper_db.get_recursive_summary(candidate_arxiv_codes)
    abstracts_str = "\n".join(
        [
            f"<{code}>\n{abstract}\n</{code}>\n"
            for code, abstract in candidate_abstracts.items()
        ]
    )
    logger.info("Selecting most interesting paper...")
    arxiv_code = vs.select_most_interesting_paper(
        abstracts_str, model="claude-3-5-sonnet-20241022"
    )
    logger.info(f"Candidate selected: {arxiv_code}")
    return arxiv_code


def select_paper(logger: logging.Logger) -> str:
    """Select a paper to tweet about."""
    candidates = fetch_candidate_papers(logger)
    arxiv_code = choose_interesting_paper(candidates, logger)
    logger.info(f"Selected paper: {arxiv_code}")
    return arxiv_code


def prepare_tweet_facts(
    arxiv_code: str, tweet_type: str, logger: logging.Logger
) -> Tuple[str, str, str]:
    """Prepare basic tweet information and content based on tweet type."""
    ## Load paper details
    paper_details = paper_db.load_arxiv(arxiv_code)
    title_map = db_utils.get_arxiv_title_dict()
    paper_title = title_map[arxiv_code]

    ## Extract metadata
    publish_date_full = paper_details["published"].iloc[0].strftime("%b %d, %Y")
    author = paper_details["authors"].iloc[0]

    ## Get content based on tweet type
    if tweet_type == "punchline":
        markdown_content, success = au.get_paper_markdown(arxiv_code)
        if not success:
            raise Exception(f"Could not load markdown content for {arxiv_code}")
        content = markdown_content
    else:
        content = paper_db.get_extended_notes(arxiv_code, expected_tokens=4500)

    tweet_facts = f"**Title: {paper_title}**\n**Authors: {author}**\n{content}"
    post_tweet = f"arxiv link: https://arxiv.org/abs/{arxiv_code}\nllmpedia link: https://llmpedia.streamlit.app/?arxiv_code={arxiv_code}"

    ## Add repository link if available.
    repo_df = paper_db.load_repositories(arxiv_code)
    if not repo_df.empty and repo_df["repo_url"].values[0]:
        repo_url = repo_df["repo_url"].values[0]
        post_tweet += f"\nrepo: {repo_url}"
        logger.info(f"Added repository link for: {arxiv_code} - '{paper_title}'")

    return tweet_facts, post_tweet, publish_date_full


def generate_tweet_content(
    tweet_type: str,
    tweet_facts: str,
    arxiv_code: str,
    publish_date: str,
    logger: logging.Logger,
) -> TweetContent:
    """Generate tweet content based on type."""
    paper_title = db_utils.get_arxiv_title_dict()[arxiv_code]

    if tweet_type == "fable":
        logger.info(f"Generating fable tweet: {arxiv_code} - '{paper_title}'")
        with open(f"{IMG_PATH}/{arxiv_code}.png", "rb") as img_file:
            b64_image = base64.b64encode(img_file.read()).decode("utf-8")

        content = vs.write_fable(
            tweet_facts=tweet_facts,
            image_data=b64_image,
            model="claude-3-7-sonnet-20250219",
            temperature=0.9,
        )
        return TweetContent(
            content=bold(content, publish_date),
            post_content=tweet_facts,
            tweet_type=tweet_type,
            arxiv_code=arxiv_code,
            publish_date=publish_date,
        )

    elif tweet_type == "punchline":
        logger.info(f"Generating punchline tweet: {arxiv_code} - '{paper_title}'")
        punchline_obj = vs.write_punchline_tweet(
            markdown_content=tweet_facts,  # Already contains markdown content
            paper_title=paper_title,
            model="claude-3-7-sonnet-20250219",
            temperature=0.9,
        )
        content = punchline_obj.line
        return TweetContent(
            content=bold(content, publish_date),
            post_content=tweet_facts,
            tweet_type=tweet_type,
            arxiv_code=arxiv_code,
            publish_date=publish_date,
            selected_image=punchline_obj.image,
            selected_table=punchline_obj.table,
        )

    else:  # insight_v5
        logger.info(f"Generating insight tweet: {arxiv_code} - '{paper_title}'")
        recent_analyses = tweet_db.read_last_n_tweet_analyses(5)
        recent_analyses_str = ""
        if not recent_analyses.empty:
            entries = []
            for _, row in recent_analyses.iterrows():
                timestamp = pd.to_datetime(row["tstp"]).strftime("%Y-%m-%d %H:%M")
                entries.append(f"[{timestamp}] {row['response'].strip()}")
            recent_analyses_str = "\n".join(entries)

        most_recent_tweets = (
            tweet_db.load_tweet_insights(drop_rejected=True)
            .head(7)["tweet_insight"]
            .values
        )
        most_recent_tweets_str = "\n".join(
            [
                f"- {tweet.replace('Insight from ', 'From ')}"
                for tweet in most_recent_tweets
            ]
        )

        tweet_obj = vs.write_tweet(
            tweet_facts=tweet_facts,
            tweet_type=tweet_type,
            most_recent_tweets=most_recent_tweets_str,
            recent_llm_tweets=recent_analyses_str,
            model="claude-3-7-sonnet-20250219",
            temperature=0.9,
        )
        content = tweet_obj.edited_tweet

        return TweetContent(
            content=bold(content, publish_date),
            post_content=tweet_facts,
            tweet_type=tweet_type,
            arxiv_code=arxiv_code,
            publish_date=publish_date,
        )


def prepare_tweet_images(
    tweet_content: TweetContent, logger: logging.Logger
) -> TweetImages:
    """Prepare images based on tweet type."""
    paper_title = db_utils.get_arxiv_title_dict()[tweet_content.arxiv_code]
    images = TweetImages()

    if tweet_content.tweet_type in ["insight_v5", "fable"]:
        ## Download art image if needed
        images.tweet_image = f"{IMG_PATH}/{tweet_content.arxiv_code}.png"
        if not os.path.exists(images.tweet_image):
            logger.info(
                f"Downloading art image: {tweet_content.arxiv_code} - '{paper_title}'"
            )
            pu.download_s3_file(
                tweet_content.arxiv_code,
                bucket_name="arxiv-art",
                prefix="data",
                format="png",
            )

    if tweet_content.tweet_type == "insight_v5":
        ## Download first page if needed
        images.tweet_page = f"{PAGE_PATH}/{tweet_content.arxiv_code}.png"
        if not os.path.exists(images.tweet_page):
            logger.info(f"Downloading first page for {tweet_content.arxiv_code}")
            pu.download_s3_file(
                tweet_content.arxiv_code,
                bucket_name="arxiv-first-page",
                prefix="data",
                format="png",
            )

        ## Get analyzed image if available
        analyzed_image = vs.analyze_paper_images(
            tweet_content.arxiv_code, model="claude-3-5-sonnet-20241022"
        )
        if analyzed_image:
            images.analyzed_image = os.path.join(
                DATA_PATH, "arxiv_md", tweet_content.arxiv_code, analyzed_image
            )
            if not os.path.exists(images.analyzed_image):
                logger.warning(f"Selected image {analyzed_image} not found")
                images.analyzed_image = None

    elif tweet_content.tweet_type == "punchline" and tweet_content.selected_image:
        ## Use selected image for punchlines
        image_path = os.path.join(
            DATA_PATH,
            "arxiv_md",
            tweet_content.arxiv_code,
            tweet_content.selected_image.split("/")[-1],
        )

        if os.path.exists(image_path):
            images.tweet_page = image_path
            logger.info(f"Using selected image: {image_path}")
        else:
            logger.warning(f"Selected image not found, falling back to first page")
            images.tweet_page = f"{PAGE_PATH}/{tweet_content.arxiv_code}.png"
            if not os.path.exists(images.tweet_page):
                pu.download_s3_file(
                    tweet_content.arxiv_code,
                    bucket_name="arxiv-first-page",
                    prefix="data",
                    format="png",
                )

    return images


def main():
    """Generate a weekly review of highlights and takeaways from papers."""
    logger.info("Starting tweet generation process.")

    ## Select tweet type
    rand_val = random.random()
    # tweet_type = (
    #     "fable" if rand_val < 0.0 else "punchline" if rand_val < 0.5 else "insight_v5"
    # )
    tweet_type = "insight_v5"
    logger.info(f"Selected tweet type: {tweet_type}")

    ## Select paper
    # arxiv_code = select_paper(logger)
    arxiv_code = "2502.17535"

    ## Prepare tweet facts and content
    tweet_facts, post_tweet, publish_date = prepare_tweet_facts(
        arxiv_code, tweet_type, logger
    )

    ## Generate tweet content based on type
    tweet_content = generate_tweet_content(
        tweet_type, tweet_facts, arxiv_code, publish_date, logger
    )
    logger.info(f"Generated content: {tweet_content.content}")

    ## Prepare images based on tweet type
    images = prepare_tweet_images(tweet_content, logger)

    ## Log image paths
    logger.info("Sending tweet with the following images:")
    logger.info(f"- tweet_image_path: {images.tweet_image}")
    logger.info(f"- tweet_page_path: {images.tweet_page}")
    logger.info(f"- analyzed_image_path: {images.analyzed_image}")

    ## Check for author's tweet
    author_tweet = None
    try:
        author_tweet = tweet.find_paper_author_tweet(arxiv_code, logger)
        if author_tweet:
            logger.info(f"Found author tweet: {author_tweet['text']}")
    except Exception as e:
        logger.warning(f"Failed to fetch author tweet: {str(e)}")

    ## Send tweet
    tweet_success = tweet.send_tweet(
        tweet_content=tweet_content.content,
        tweet_image_path=images.tweet_image,
        post_tweet=post_tweet,
        logger=logger,
        author_tweet=author_tweet,
        tweet_page_path=images.tweet_page,
        analyzed_image_path=images.analyzed_image,
        verify=True,
        headless=False,
    )

    ## Store results
    if tweet_success:
        tweet_db.insert_tweet_review(
            arxiv_code,
            tweet_content.content,
            datetime.datetime.now(),
            tweet_type,
            rejected=False,
        )
        em.send_email_alert(tweet_content.content, arxiv_code)
        logger.info("Tweet stored in database and email alert sent.")
    else:
        logger.error("Failed to send tweet.")


if __name__ == "__main__":
    main()
