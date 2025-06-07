# Functions for generating tweet content and selecting tweet types 

import os
import sys
import base64
import random
import logging
from typing import Optional, List, Tuple, Protocol
from dotenv import load_dotenv

## Assuming necessary setup for PROJECT_PATH is done elsewhere or passed
## Need to handle logger setup, perhaps pass logger instance into functions
logger = logging.getLogger(__name__)

## Constants - Consider defining these globally or passing them
DEFAULT_MODEL = "claude-3-5-sonnet-20241022" # Or fetch from env

## Assuming these utils are available
import utils.app_utils as au
import utils.vector_store as vs
import utils.db.paper_db as paper_db
from utils.tweet import bold, boldify, find_paper_author_tweet, TweetThreadConfig
from utils.vector_store import verify_punchline_image_relevance
from utils.image_utils import ImageManager

## Define the uniform generator interface
class TweetPartGenerator(Protocol):
    def __call__(
        self,
        *,
        arxiv_code: str,
        paper_details: dict,
        img_mgr: ImageManager,
        logger: logging.Logger,
    ) -> Tuple[Optional[str], Optional[List[str]]]:
        ...

def generate_punchline_parts(
    arxiv_code: str, paper_details: dict, img_mgr: ImageManager, logger: logging.Logger
) -> tuple[Optional[str], Optional[List[str]]]:
    """Generate content and image path(s) for a punchline tweet."""
    markdown_content, success = au.get_paper_markdown(arxiv_code)
    if not success:
        logger.error(f"Could not load markdown content for {arxiv_code}")
        return None, None  # Or raise an exception?

    try:
        punchline_obj = vs.write_punchline_tweet(
            markdown_content=markdown_content,
            paper_title=paper_details["title"],
            model=DEFAULT_MODEL,
            temperature=0.9,
        )
    except Exception as e:
        logger.error(f"Error calling vs.write_punchline_tweet for {arxiv_code}: {e}")
        return None, None

    publish_date = paper_details["published"].strftime("%b %d, %Y")
    content = bold(punchline_obj.line, publish_date)

    ## Process image
    images = []
    if punchline_obj.image:
        ## Get image path
        image_path = img_mgr.get_image_path(
            arxiv_code, "figure", punchline_obj.image
        )
        
        if image_path:
            ## Read image and convert to base64
            with open(image_path, "rb") as img_file:
                b64_image = base64.b64encode(img_file.read()).decode("utf-8")
            
            ## Verify relevance
            logger.info(f"Verifying relevance for image {punchline_obj.image} and punchline '{punchline_obj.line}'...")
            relevance_result = verify_punchline_image_relevance(
                punchline_text=punchline_obj.line,
                image_data=b64_image,
                model=DEFAULT_MODEL,
            )
            
            if relevance_result.is_relevant:
                logger.info(f"Image {punchline_obj.image} deemed relevant. Adding to tweet.")
                images.append(image_path)
            else:
                logger.warning(
                    f"Punchline image {punchline_obj.image} deemed irrelevant for punchline '{punchline_obj.line}'. "
                    f"Explanation: {relevance_result.explanation}. Discarding."
                )
        else:
            logger.warning(
                f"Selected punchline image {punchline_obj.image} not found for {arxiv_code}"
            )

    return content, images or None


def generate_insight_parts(
    arxiv_code: str, paper_details: dict, img_mgr: ImageManager, logger: logging.Logger
) -> tuple[Optional[str], Optional[List[str]]]:
    """Generate content and image path(s) for an insight tweet."""
    try:
        tweet_facts = prepare_tweet_facts(arxiv_code, "insight_v5")
        tweet_obj = vs.write_tweet(
            tweet_facts=tweet_facts,
            llm_model=DEFAULT_MODEL,
            temperature=0.9,
        )
    except Exception as e:
        logger.error(f"Error generating insight content for {arxiv_code}: {e}")
        return None, None

    publish_date = paper_details["published"].strftime("%b %d, %Y")
    content = bold(tweet_obj.edited_tweet, publish_date)

    ## Get art image
    images = []
    art_image = img_mgr.get_image_path(arxiv_code, "art")
    if art_image:
        images.append(art_image)
    else:
        logger.warning(f"Art image not found for {arxiv_code} (insight tweet)")

    ## Get first page image
    first_page_image = img_mgr.get_image_path(arxiv_code, "first_page")
    if first_page_image:
        images.append(first_page_image)
    else:
        logger.warning(f"First page image not found for {arxiv_code} (insight tweet)")

    return content, images or None


def generate_fable_parts(
        
    arxiv_code: str, paper_details: dict, img_mgr: ImageManager, logger: logging.Logger
) -> tuple[Optional[str], Optional[List[str]]]:
    """Generate content and image path(s) for a fable tweet."""
    ## Get art image first since we need it for content generation
    art_image = img_mgr.get_image_path(arxiv_code, "art")
    if not art_image:
        logger.error(f"Could not find art image for {arxiv_code} (fable tweet)")
        return None, None

    try:
        with open(art_image, "rb") as img_file:
            b64_image = base64.b64encode(img_file.read()).decode("utf-8")

        tweet_facts = prepare_tweet_facts(arxiv_code, "fable")
        content_text = vs.write_fable(
            tweet_facts=tweet_facts,
            image_data=b64_image,
            model=DEFAULT_MODEL,
            temperature=0.9,
        )
    except Exception as e:
        logger.error(f"Error generating fable content for {arxiv_code}: {e}")
        return None, None

    publish_date = paper_details["published"].strftime("%b %d, %Y")
    content = bold(content_text, publish_date)
    images = [art_image]

    return content, images


def prepare_tweet_facts(arxiv_code: str, tweet_type: str) -> str:
    """Prepare tweet facts based on tweet type."""
    if tweet_type == "fable":
        markdown_content, success = au.get_paper_markdown(arxiv_code)
        if not success:
            raise Exception(f"Could not load markdown content for {arxiv_code}")
        return markdown_content
    else:
        # Assume au.get_paper_markdown works for insight as well based on z2 logic
        # If specific fields are needed, load from paper_db
        paper_details = paper_db.load_arxiv(arxiv_code)
        if paper_details.empty:
             raise Exception(f"Could not load paper details for {arxiv_code}")
        title = paper_details["title"].iloc[0]
        author = paper_details["authors"].iloc[0]
        content, success = au.get_paper_markdown(arxiv_code)
        if not success:
            raise Exception(f"Could not load markdown content for {arxiv_code}")
        return f"**Title: {title}**\n**Authors: {author}**\n{content}"


def generate_links_content(arxiv_code: str, paper_details: dict) -> str:
    """Generate the standard links tweet content."""
    paper_title = paper_details.get("title", "Unknown Title")
    content_lines = [
        f"From: {boldify(paper_title)}",
        f"arxiv link: https://arxiv.org/abs/{arxiv_code}",
        f"llmpedia link: https://llmpedia.ai/?arxiv_code={arxiv_code}",
    ]

    ## Add repository link if available
    try:
        repo_df = paper_db.load_repositories(arxiv_code)
        if not repo_df.empty and repo_df["repo_url"].values[0]:
            content_lines.append(f"repo: {repo_df['repo_url'].values[0]}")
    except Exception as e:
        logger.warning(f"Could not load repository info for {arxiv_code}: {e}")

    return "\n".join(content_lines)


def generate_author_tweet_content(arxiv_code: str, logger: Optional[logging.Logger] = None) -> str:
    """Generate content pointing to a related author tweet, if found."""
    author_tweet = find_paper_author_tweet(arxiv_code, logger)
    if author_tweet and author_tweet.get("link"):
        return f"related discussion: {author_tweet['link']}"
    else:
        return ""  # Return empty string if not found or error occurs


## Adapter functions for text-only generators
def links_parts(*, arxiv_code: str, paper_details: dict, img_mgr: ImageManager, logger: logging.Logger):
    # Need to pass logger if generate_links_content requires it (currently doesn't)
    return generate_links_content(arxiv_code, paper_details), None

def author_parts(*, arxiv_code: str, paper_details: dict, img_mgr: ImageManager, logger: logging.Logger):
     # Pass logger to generate_author_tweet_content
    return generate_author_tweet_content(arxiv_code, logger=logger), None

## Adapter function for image-only generators
def art_only(*, arxiv_code: str, paper_details: dict, img_mgr: ImageManager, logger: logging.Logger):
    path = img_mgr.get_image_path(arxiv_code, "art")
    # Return "" for content, as specified in the plan.
    return "", [path] if path else None

## Generator Registry
GENERATOR_REGISTRY: dict[str, TweetPartGenerator] = {
    "punchline": generate_punchline_parts,
    "insight":   generate_insight_parts,
    "fable":     generate_fable_parts,
    "links":     links_parts,
    "author":    author_parts,
    "art":       art_only,
}

def select_tweet_type(config_data: dict) -> str:
    """Select a tweet type randomly based on configured weights."""
    ## Extract necessary config sections
    selection_config = config_data.get("selection", {})
    tweet_type_configs = config_data.get("tweet_types", {})

    ## Use default weights or weights from tweet type configs
    weights_dict = selection_config.get("default_weights", {})

    if not weights_dict:
         # Need TweetThreadConfig definition from utils.tweet
        weights_dict = {t: TweetThreadConfig(**config).weight for t, config in tweet_type_configs.items()}

    ## Keep only valid tweet types present in tweet_types
    weights_dict = {t: w for t, w in weights_dict.items() if t in tweet_type_configs}

    if not weights_dict:
        raise ValueError("No valid tweet types found in configuration")

    ## Normalize weights
    total_weight = sum(weights_dict.values())
    if total_weight <= 0:
        raise ValueError(f"Total weight must be positive, got {total_weight}")

    ## Select tweet type based on normalized weights
    tweet_types = list(weights_dict.keys())
    weights = [w / total_weight for w in weights_dict.values()]

    return random.choices(tweet_types, weights=weights, k=1)[0] 