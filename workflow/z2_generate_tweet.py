#!/usr/bin/env python3

# import datetime ## No longer needed for insert_tweet_review
import os
import sys
import argparse
from typing import Optional, List
import yaml
from dotenv import load_dotenv
import logging
# import pprint # Removed for dry run

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
load_dotenv(os.path.join(PROJECT_PATH, ".env"))
sys.path.append(PROJECT_PATH)

DATA_PATH = os.path.join(PROJECT_PATH, "data")
IMG_PATH = os.path.join(DATA_PATH, "arxiv_art")
PAGE_PATH = os.path.join(DATA_PATH, "arxiv_first_page")

## Constants
DEFAULT_MODEL = "claude-3-7-sonnet-20250219"
SELECTOR_MODEL = "gemini/gemini-2.5-pro-preview-05-06"

from utils.logging_utils import setup_logger
import utils.vector_store as vs
import utils.paper_utils as pu
# import utils.notifications as em ## Removed, email sent by z4
import utils.db.db_utils as db_utils
import utils.db.paper_db as paper_db
import utils.db.tweet_db as tweet_db

## Import the necessary components from utils.tweet
from utils.tweet import (
    TweetThreadConfig,
    Tweet,
    TweetThread,
    # send_tweet2, ## Removed, posting handled by z4
)

## NEW IMPORTS
from utils.image_utils import ImageManager
import utils.tweet_generators as tg

logger = setup_logger(__name__, "z2_generate_tweet.log")

##########################
## CONTENT GENERATORS   ##
##########################

# Functions moved to utils/tweet_generators.py

##########################
## HELPER FUNCTIONS     ##
##########################

# Functions moved to utils/tweet_generators.py

def select_paper() -> str:
    """Select a paper to tweet about."""
    candidates = fetch_candidate_papers(logger)
    arxiv_code = choose_interesting_paper(candidates, logger)
    return arxiv_code


def fetch_candidate_papers(logger) -> List[str]:
    """Fetch candidates from S3 excluding already reviewed papers."""
    arxiv_codes = pu.list_s3_files("arxiv-art", strip_extension=True)
    
    # Get papers that have already been posted (from tweet_reviews table)
    posted_codes = db_utils.get_arxiv_id_list("tweet_reviews")
    
    # Get papers that are currently pending (to avoid duplicates)
    pending_codes = db_utils.get_arxiv_id_list("pending_tweets")
    
    # Exclude both posted and pending papers
    done_codes = set(posted_codes + pending_codes)
    candidates = list(set(arxiv_codes) - done_codes)
    candidates = sorted(candidates)[-100:]  # Limit to most recent 100
    
    logger.info(f"Found {len(posted_codes)} already posted papers")
    logger.info(f"Found {len(pending_codes)} papers with pending tweets") 
    logger.info(f"Found {len(candidates)} recent papers to consider")
    return candidates


def choose_interesting_paper(candidates: List[str], logger) -> str:
    """Select the most interesting candidate paper based on citations."""
    citations_df = paper_db.load_citations()
    citations_df = citations_df[citations_df.index.isin(candidates)]
    citations_df["citation_count"] = citations_df["citation_count"].fillna(1) + 1
    citations_df["weight"] = (
        citations_df["citation_count"] / citations_df["citation_count"].sum()
    ) ** 0.5
    citations_df["weight"] = citations_df["weight"] / citations_df["weight"].sum()

    # Need random import here now
    import random
    candidate_arxiv_codes = random.choices(
        citations_df.index, weights=citations_df["weight"], k=25
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
    arxiv_code = vs.select_most_interesting_paper(abstracts_str, llm_model=SELECTOR_MODEL)
    logger.info(f"Candidate selected: {arxiv_code}")
    return arxiv_code


##########################
## TWEET BUILDER        ##
##########################

def build_tweet_thread(
    tweet_type: str,
    arxiv_code: str,
    tweet_type_config: TweetThreadConfig, # Uses updated TweetConfig internally
    image_manager: ImageManager, # Keep this name for the argument
    logger: logging.Logger
) -> TweetThread:
    """Generate a complete tweet thread using the generator registry."""
    paper_details_df = paper_db.load_arxiv(arxiv_code)
    if paper_details_df.empty:
        raise ValueError(f"Could not load paper details for {arxiv_code}")
    paper_details = paper_details_df.iloc[0].to_dict()

    tweets = []
    generated_parts_cache = {} ## Cache: Key = (generator_name, arxiv_code), Value = (content, images)

    ## Pass ImageManager as img_mgr to generators
    img_mgr = image_manager

    ## New loop using generator registry
    for tweet_cfg in tweet_type_config.tweets:
        gen_name = tweet_cfg.generator
        content = None
        images = None

        logger.info(f"Processing generator: {gen_name} for position {tweet_cfg.position}")

        ## Handle special cases if any (e.g., 'first_page')
        if gen_name == "first_page":
            img_path = img_mgr.get_image_path(arxiv_code, "first_page")
            if img_path:
                content, images = "", [img_path] # Content is empty for first_page image
            else:
                logger.warning(f"First page image not found for {arxiv_code}, skipping.")
                continue
        elif gen_name in tg.GENERATOR_REGISTRY:
            gen = tg.GENERATOR_REGISTRY[gen_name]
            cache_key = (gen_name, arxiv_code) # Use tuple for cache key

            if cache_key not in generated_parts_cache:
                logger.info(f"Calling generator '{gen_name}' for {arxiv_code}...")
                try:
                    ## Call the generator, passing img_mgr
                    generated_parts_cache[cache_key] = gen(
                        arxiv_code=arxiv_code,
                        paper_details=paper_details,
                        img_mgr=img_mgr, # Pass the renamed variable
                        logger=logger,
                    )
                except Exception as e:
                    logger.error(f"Error running generator '{gen_name}' for {arxiv_code}: {e}", exc_info=True)
                    generated_parts_cache[cache_key] = (None, None) # Cache failure

            content, images = generated_parts_cache[cache_key]
        else:
            logger.error(f"Unknown generator name '{gen_name}' found in config for position {tweet_cfg.position}. Skipping.")
            continue # Skip if generator not found

        ## Check if the generator produced anything
        if not content and not images:
            logger.info(f"Generator '{gen_name}' produced no content or images for position {tweet_cfg.position}. Skipping tweet.")
            continue

        ## Create Tweet Object
        tweets.append(
            Tweet(
                content=content or "", # Ensure content is at least an empty string
                images=images,
                position=tweet_cfg.position
            )
        )

    ## Return TweetThread
    if not tweets:
         logger.warning(f"No tweets generated for {arxiv_code} (type: {tweet_type}). Returning empty thread.")

    return TweetThread(
        arxiv_code=arxiv_code,
        tweet_type=tweet_type,
        tweets=sorted(tweets, key=lambda t: t.position), ## Ensure correct order
    )


def main():
    """Main function to generate and send tweets using functional approach."""
    ## Parse command line arguments.
    parser = argparse.ArgumentParser(
        description="Generate and send tweets about papers"
    )
    parser.add_argument(
        "--tweet-type", help="Specific tweet type to use (overrides random selection)"
    )
    # parser.add_argument(
    #     "--dry-run",
    #     action="store_true",
    #     help="Generate tweet thread but do not send it; print instead."
    # ) ## Removed dry-run argument
    args = parser.parse_args()

    logger.info("Starting tweet generation process")

    ## Load configuration.
    config_path = "config/tweet_types.yaml"
    try:
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
        if not config_data or "tweet_types" not in config_data:
             raise ValueError("Config file is empty or missing 'tweet_types' key")
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML configuration: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
        
    image_manager = ImageManager(DATA_PATH)

    ## Select tweet type using configured weights or use specified type.
    if args.tweet_type:
        if args.tweet_type not in config_data.get("tweet_types", {}):
            logger.error(f"Unknown tweet type specified: {args.tweet_type}")
            sys.exit(1)
        tweet_type = args.tweet_type
        logger.info(f"Using specified tweet type: {tweet_type}")
    else:
        try:
            tweet_type = tg.select_tweet_type(config_data)
            logger.info(f"Selected tweet type: {tweet_type}")
        except ValueError as e:
            logger.error(f"Error selecting tweet type: {str(e)}")
            sys.exit(1)

    ## Select paper.
    arxiv_code = select_paper()
    logger.info(f"Selected paper: {arxiv_code}")

    try:
        ## Load the specific config for the selected tweet type
        tweet_type_cfg_dict = config_data["tweet_types"][tweet_type]
        tweet_type_config = TweetThreadConfig.model_validate(tweet_type_cfg_dict)

        ## Build the tweet thread.
        logger.info(f"Building tweet thread of type '{tweet_type}' for {arxiv_code}")
        thread: TweetThread = build_tweet_thread(
            tweet_type,
            arxiv_code,
            tweet_type_config, # Pass the validated config object
            image_manager, # Pass the ImageManager instance
            logger
        )

        if not thread or not thread.tweets:
            logger.warning(f"No tweets were generated for {arxiv_code}. Exiting.")
            sys.exit(0) # Exit gracefully if no tweets generated

        ## Store the generated thread as pending
        logger.info(f"Storing generated thread for {arxiv_code} as pending.")
        try:
            success = tweet_db.store_pending_tweet(
                arxiv_code=arxiv_code,
                tweet_type=tweet_type,
                thread=thread
            )
            if not success:
                 logger.error(f"Failed to store pending tweet for {arxiv_code}. Exiting.")
                 sys.exit(1)
            else:
                 logger.info(f"Successfully stored pending tweet for {arxiv_code} (type: {tweet_type}).")
        except Exception as e:
            logger.error(f"Database error storing pending tweet for {arxiv_code}: {e}", exc_info=True)
            sys.exit(1)

        ## Removed dry-run check, sending logic, tweet review insertion, and email alert
        # if args.dry_run:
        #     logger.info("Dry run requested. Printing generated thread:")
        #     pprint.pprint(thread.model_dump())
        #     sys.exit(0)
        # else:
        #     logger.info(f"Attempting to send tweet for {arxiv_code}")
        #     success = send_tweet2(thread, logger, image_manager.local_prefix, IMG_PATH)
        #     if success:
        #         logger.info(f"Successfully sent tweet for {arxiv_code}.")
        #         # Store the review
        #         first_tweet_content = thread.tweets[0].content if thread.tweets else ""
        #         tweet_db.insert_tweet_review(
        #             arxiv_code=arxiv_code,
        #             review=first_tweet_content,
        #             tstp=datetime.datetime.now(),
        #             tweet_type=tweet_type,
        #             rejected=False
        #         )
        #         # Send email alert
        #         em.send_email_alert(first_tweet_content, arxiv_code)
        #         logger.info(f"Email alert sent for {arxiv_code}.")
        #     else:
        #         logger.error(f"Failed to send tweet for {arxiv_code}. Exiting.")
        #         sys.exit(1)

    except ValueError as e:
        logger.error(f"Value Error during tweet generation for {arxiv_code}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during tweet generation for {arxiv_code}: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Tweet generation process completed successfully.")


if __name__ == "__main__":
    main()
