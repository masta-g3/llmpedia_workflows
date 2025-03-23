import pandas as pd
import os
import re
import base64
import requests
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken
from typing import Optional, Tuple

import utils.prompts as ps
import utils.pydantic_objects as po
import utils.app_utils as au
import utils.db.paper_db as paper_db
from utils.instruct import run_instructor_query, format_vision_messages

token_encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")


def validate_openai_env() -> None:
    """Validate that the API base is not set to local."""
    api_base = os.environ.get("OPENAI_API_BASE", "")
    false_base = "http://localhost:1234/v1"
    assert api_base != false_base, "API base is not set to local."


###################
## SUMMARIZATION ##
###################

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=5000, chunk_overlap=50
)


def recursive_summarize_by_parts(
    paper_title: str,
    document: str,
    max_tokens=400,
    model="local",
    mlx_model=None,
    mlx_tokenizer=None,
    verbose=False,
):
    """Recursively apply the summarize_by_segments function to a document."""

    ori_token_count = len(token_encoder.encode(document))
    token_count = ori_token_count + 0
    if verbose:
        print(f"Starting tokens: {ori_token_count}")
    summaries_dict = {}
    token_dict = {}
    retry_once = True
    i = 1

    while token_count > max_tokens:
        if verbose:
            print("------------------------")
            print(f"Summarization iteration {i}...")
        document = summarize_by_parts(
            paper_title, document, model, mlx_model, mlx_tokenizer, verbose
        )

        token_diff = token_count - len(token_encoder.encode(document))
        token_count = len(token_encoder.encode(document))
        frac = token_count / ori_token_count
        summaries_dict[i] = document
        token_dict[i] = token_count
        i += 1
        if verbose:
            print(f"Total tokens: {token_count}")
            print(f"Compression: {frac:.2f}")

        if token_diff < 50:
            if retry_once:
                retry_once = False
                continue
            else:
                if verbose:
                    print("Cannot compress further. Stopping.")
                break

    return summaries_dict, token_dict


def summarize_by_parts(
    paper_title: str,
    document: str,
    model="mlx",
    mlx_model=None,
    mlx_tokenizer=None,
    verbose=False,
):
    """Summarize a paper by segments."""
    doc_chunks = text_splitter.create_documents([document])
    summary_notes = ""
    st_time = pd.Timestamp.now()
    for idx, current_chunk in enumerate(doc_chunks):
        summary_notes += (
            au.numbered_to_bullet_list(
                summarize_doc_chunk_mlx(
                    paper_title, current_chunk, mlx_model, mlx_tokenizer
                )
                if model == "mlx"
                else summarize_doc_chunk(paper_title, current_chunk, model)
            )
            + "\n"
        )
        if verbose:
            time_elapsed = pd.Timestamp.now() - st_time
            print(
                f"{idx+1}/{len(doc_chunks)}: {time_elapsed.total_seconds():.2f} seconds"
            )
            st_time = pd.Timestamp.now()

    return summary_notes


def summarize_doc_chunk(paper_title: str, document: str, model="local"):
    """Summarize a paper by segments."""
    summary = run_instructor_query(
        ps.SUMMARIZE_BY_PARTS_SYSTEM_PROMPT,
        ps.SUMMARIZE_BY_PARTS_USER_PROMPT.format(content=document),
        llm_model=model,
        process_id="summarize_doc_chunk",
    )
    summary = summary.strip()
    if "<summary>" in summary:
        summary = summary.split("<summary>")[1].split("</summary>")[0]
    return summary


def summarize_doc_chunk_mlx(paper_title: str, document: str, mlx_model, mlx_tokenizer):
    """Summarize a paper by segments with MLX models."""
    from mlx_lm import generate

    messages = [
        ("system", ps.SUMMARIZE_BY_PARTS_SYSTEM_PROMPT.format(paper_title=paper_title)),
        ("user", ps.SUMMARIZE_BY_PARTS_USER_PROMPT.format(content=document)),
    ]
    messages = [{"role": role, "content": content} for role, content in messages]

    prompt = mlx_tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    summary = generate(
        mlx_model,
        mlx_tokenizer,
        prompt=prompt,
        max_tokens=500,
        # repetition_penalty=1.05,
        verbose=False,
    )

    return summary


def verify_llm_paper(paper_content: str, model="gpt-4o"):
    """Verify if a paper is about LLMs."""
    is_llm_paper = run_instructor_query(
        ps.LLM_VERIFIER_SYSTEM_PROMPT,
        ps.LLM_VERIFIER_USER_PROMPT.format(paper_content=paper_content),
        model=po.LLMVerifier,
        llm_model=model,
        process_id="verify_llm_paper",
    )
    is_llm_paper = is_llm_paper.dict()
    return is_llm_paper


def review_llm_paper(paper_content: str, model="gpt-4o"):
    """Review a paper."""
    review = run_instructor_query(
        ps.SUMMARIZER_SYSTEM_PROMPT,
        ps.SUMMARIZER_USER_PROMPT.format(paper_content=paper_content),
        model=po.PaperReview,
        llm_model=model,
        process_id="review_llm_paper",
    )
    return review


def convert_notes_to_narrative(
    paper_title: str, notes: str, model: str = "gpt-4o"
) -> str:
    """Convert notes to narrative."""
    narrative = run_instructor_query(
        ps.NARRATIVE_SUMMARY_SYSTEM_PROMPT.format(paper_title=paper_title),
        ps.NARRATIVE_SUMMARY_USER_PROMPT.format(previous_notes=notes),
        llm_model=model,
        process_id="convert_notes_to_narrative",
    )
    if "<summary>" in narrative:
        narrative = narrative.split("<summary>")[1].split("</summary>")[0]
    return narrative


def convert_notes_to_bullets(
    paper_title: str, notes: str, model: str = "GPT-3.5-Turbo"
) -> str:
    """Convert notes to bullet point list."""
    bullet_list = run_instructor_query(
        ps.BULLET_LIST_SUMMARY_SYSTEM_PROMPT,
        ps.BULLET_LIST_SUMMARY_USER_PROMPT.format(
            paper_title=paper_title, previous_notes=notes
        ),
        llm_model=model,
        process_id="convert_notes_to_bullets",
    ).strip()
    if "<summary>" in bullet_list:
        bullet_list = bullet_list.split("<summary>")[1].split("</summary>")[0]
    return bullet_list


def copywrite_summary(paper_title, previous_notes, narrative, model="GPT-3.5-Turbo"):
    """Copywrite a summary."""
    copywritten = run_instructor_query(
        ps.COPYWRITER_SYSTEM_PROMPT,
        ps.COPYWRITER_USER_PROMPT.format(
            paper_title=paper_title,
            previous_notes=previous_notes,
            previous_summary=narrative,
        ),
        llm_model=model,
        process_id="copywrite_summary",
    )
    if "<improved_summary>" in copywritten:
        copywritten = copywritten.split("<improved_summary>")[1].split(
            "</improved_summary>"
        )[0]
    return copywritten


def organize_notes(paper_title, notes, model="GPT-3.5-Turbo"):
    """Add header titles and organize notes."""
    organized_sections = run_instructor_query(
        ps.FACTS_ORGANIZER_SYSTEM_PROMPT,
        ps.FACTS_ORGANIZER_USER_PROMPT.format(
            paper_title=paper_title, previous_notes=notes
        ),
        llm_model=model,
        process_id="organize_notes",
    )
    return organized_sections


def convert_notes_to_markdown(paper_title, notes, model="GPT-3.5-Turbo"):
    """Convert notes to markdown."""
    markdown = run_instructor_query(
        ps.MARKDOWN_SYSTEM_PROMPT.format(paper_title=paper_title),
        ps.MARKDOWN_USER_PROMPT.format(previous_notes=notes),
        llm_model=model,
        process_id="convert_notes_to_markdown",
    )
    return markdown


def rephrase_title(title, model="gpt-4o"):
    """Summarize a title as a short visual phrase."""
    phrase = run_instructor_query(
        ps.TITLE_REPHRASER_SYSTEM_PROMPT,
        ps.TITLE_REPHRASER_USER_PROMPT.format(title=title),
        llm_model=model,
        temperature=1.0,
        process_id="rephrase_title",
    ).strip()
    return phrase


def generate_weekly_report(weekly_content_md: str, model="claude-3-5-sonnet-20250222"):
    """Generate weekly report."""
    weekly_report = run_instructor_query(
        ps.WEEKLY_SYSTEM_PROMPT,
        ps.WEEKLY_USER_PROMPT.format(weekly_content=weekly_content_md),
        # model=po.WeeklyReview,
        llm_model=model,
        temperature=1,
        process_id="generate_weekly_report",
        thinking={"type": "enabled", "budget_tokens": 8192},
        max_tokens=50000,
    )
    return weekly_report


def generate_weekly_highlight(weekly_content_md: str, model="claude-3-5-sonnet-20250222"):
    """Generate weekly highlight."""
    weekly_highlight = run_instructor_query(
        ps.WEEKLY_SYSTEM_PROMPT,
        ps.WEEKLY_HIGHLIGHT_USER_PROMPT.format(weekly_content=weekly_content_md),
        llm_model=model,
        temperature=0.5,
        process_id="generate_weekly_highlight",
    )
    return weekly_highlight


def extract_document_repo(paper_content: str, model="gpt-4o"):
    """Extract weekly repos."""
    weekly_repos = run_instructor_query(
        ps.REPO_EXTRACTOR_SYSTEM_PROMPT,
        ps.REPO_EXTRACTOR_USER_PROMPT.format(content=paper_content),
        llm_model=model,
        model=po.ExternalResources,
        temperature=0.0,
        process_id="extract_document_repo",
    )
    return weekly_repos

def select_most_interesting_paper(
    arxiv_abstracts: str,
    model: str = "claude-3-5-sonnet-20241022",
) -> str:
    """Select the most interesting paper from a list of candidates."""
    ## Set the abstracts on the model class for validation.
    po.InterestingPaperSelection._abstracts = arxiv_abstracts

    response = run_instructor_query(
        ps.INTERESTING_SYSTEM_PROMPT,
        ps.INTERESTING_USER_PROMPT.format(abstracts=arxiv_abstracts),
        model=po.InterestingPaperSelection,
        llm_model=model,
        process_id="select_most_interesting_paper",
    )

    ## Clean up class variable.
    delattr(po.InterestingPaperSelection, "_abstracts")

    return response.selected_arxiv_code


def write_tweet(
    tweet_facts: str,
    tweet_type="new_review",
    model="claude-3-5-sonnet-20241022",
    most_recent_tweets: str = None,
    recent_llm_tweets: str = None,
    temperature: float = 0.8,
) -> po.Tweet:
    """Write a tweet about an LLM paper."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_INSIGHT_USER_PROMPT.format(
        tweet_facts=tweet_facts,
        most_recent_tweets=most_recent_tweets,
        recent_llm_tweets=recent_llm_tweets,
        base_style=ps.TWEET_BASE_STYLE,
    )
    tweet = run_instructor_query(
        system_prompt,
        user_prompt,
        model=po.Tweet,
        llm_model=model,
        temperature=temperature,
        process_id="write_tweet",
    )
    return tweet


def write_tweet_reply(
    paper_summaries: str,
    recent_llm_tweets: str,
    tweet_threads: str,
    recent_tweet_discussions: str,
    model: str = "claude-3-7-sonnet-20250219",
    temperature: float = 0.8,
    thinking: bool = True,
) -> po.Tweet:
    """Write a reply tweet that connects papers with community discussions."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_REPLY_USER_PROMPT.format(
        paper_summaries=paper_summaries,
        recent_llm_tweets=recent_llm_tweets,
        tweet_threads=tweet_threads,
        recent_tweet_discussions=recent_tweet_discussions,
        base_style=ps.TWEET_BASE_STYLE,
    )
    kwargs = {}
    if thinking:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 1024}
    
    tweet = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=temperature if not thinking else 1.0,
        process_id="write_tweet_reply",
        verbose=True,
        **kwargs
    )
    return tweet


def select_tweet_reply(recent_llm_tweets: str,  
                       recent_tweet_discussions: str,
                       model: str = "claude-3-7-sonnet-20250219"):
    """Select a tweet reply."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_SELECTOR_USER_PROMPT.format(
        recent_llm_tweets=recent_llm_tweets,
        recent_tweet_discussions=recent_tweet_discussions,
    )
    response = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=1,
        process_id="select_tweet_reply",
    )
    return response


def write_tweet_reply_academic(
    selected_post: str,
    context: str,
    summary_of_recent_discussions: str,
    previous_posts: str,
    model: str = "claude-3-7-sonnet-20250219",
    temperature: float = 0.8,
) -> str:
    """Write a reply tweet that connects papers with community discussions."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_REPLY_ACADEMIC_USER_PROMPT.format(
        summary_of_recent_discussions=summary_of_recent_discussions,
        selected_post=selected_post,
        context=context,
        base_style=ps.TWEET_BASE_STYLE,
        previous_posts=previous_posts,
    )
    response = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=temperature,
        process_id="write_tweet_reply_academic",
        thinking={"type": "enabled", "budget_tokens": 2048},
    )
    return response


def write_tweet_reply_funny(
    selected_post: str,
    summary_of_recent_discussions: str,
    previous_posts: str,
    model: str = "claude-3-7-sonnet-20250219",
    temperature: float = 0.9,
) -> str:
    """Write a humorous, light-hearted reply tweet."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_REPLY_FUNNY_USER_PROMPT.format(
        summary_of_recent_discussions=summary_of_recent_discussions,
        selected_post=selected_post,
        base_style=ps.TWEET_BASE_STYLE,
        previous_posts=previous_posts,
    )
    response = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=temperature,
        process_id="write_tweet_reply_funny",
    )
    return response


def write_tweet_reply_commonsense(
    selected_post: str,
    summary_of_recent_discussions: str,
    previous_posts: str,
    model: str = "claude-3-7-sonnet-20250219",
    temperature: float = 0.8,
) -> str:
    """Write a reply tweet based on common-sense insights."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_REPLY_COMMONSENSE_USER_PROMPT.format(
        summary_of_recent_discussions=summary_of_recent_discussions,
        selected_post=selected_post,
        base_style=ps.TWEET_BASE_STYLE,
        previous_posts="N/A",
    )
    response = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=temperature,
        process_id="write_tweet_reply_commonsense",
    )
    return response


def write_paper_matcher(
    tweet_text: str,
    paper_summaries: str,
    previous_responses: str,
    model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.8,
) -> str:
    """Write a paper matcher."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_PAPER_MATCHER_USER_PROMPT.format(
        tweet_text=tweet_text,
        paper_summaries=paper_summaries,
        base_style=ps.TWEET_BASE_STYLE,
        previous_responses=previous_responses
    )
    response = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=temperature,
        process_id="write_paper_matcher",
    )
    return response


def write_fable(
    tweet_facts: str,
    image_data: Optional[str] = None,
    model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.8,
) -> str:
    """Generate an Aesop-style fable from a paper summary and optionally its thumbnail image."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = ps.TWEET_FABLE_USER_PROMPT.format(tweet_facts=tweet_facts)

    if image_data:
        # If image is provided, use vision API format
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_data,
                },
            },
            {
                "type": "text",
                "text": user_prompt,
            },
        ]
        messages = [{"role": "user", "content": content}]
        fable = run_instructor_query(
            system_message=system_prompt,
            user_message="",  # Not used when messages is provided
            llm_model=model,
            temperature=temperature,
            process_id="write_fable",
            messages=messages,
        )
    else:
        # Fallback to text-only format
        fable = run_instructor_query(
            system_prompt,
            user_prompt,
            llm_model=model,
            temperature=temperature,
            process_id="write_fable",
        )

    return fable.strip()


def write_punchline_tweet(
    markdown_content: str,
    paper_title: str,
    model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.8,
) -> po.PunchlineSummary:
    """Generate a punchline summary and select a relevant image from a paper's markdown content."""
    punchline = run_instructor_query(
        ps.TWEET_SYSTEM_PROMPT,
        ps.TWEET_PUNCHLINE_USER_PROMPT.format(
            paper_title=paper_title,
            markdown_content=markdown_content,
            base_style=ps.TWEET_BASE_STYLE,
        ),
        model=po.PunchlineSummary,
        llm_model=model,
        temperature=temperature,
        process_id="write_punchline",
    )

    return punchline


def edit_tweet(
    tweet: str,
    most_recent_tweets: str,
    tweet_type="review",
    model="gpt-4o",
    temperature: float = 0.8,
) -> str:
    """Edit a tweet via run_instructor_query."""
    system_prompt = ps.TWEET_SYSTEM_PROMPT
    user_prompt = tweet_edit_user_map[tweet_type].format(
        proposed_tweet=tweet, most_recent_tweets=most_recent_tweets
    )
    edited_tweet = run_instructor_query(
        system_prompt,
        user_prompt,
        llm_model=model,
        temperature=temperature,
        model=po.TweetEdit,
        process_id="edit_tweet",
    )
    return edited_tweet


def assess_tweet_ownership(
    paper_title: str,
    paper_authors: str,
    tweet_text: str,
    tweet_username: str,
    model: str = "gpt-4o",
):
    """Assess if a tweet is owned by LLMpedia."""
    system_prompt = ps.TWEET_OWNERSHIP_SYSTEM_PROMPT
    user_prompt = ps.TWEET_OWNERSHIP_USER_PROMPT.format(
        paper_title=paper_title,
        paper_authors=paper_authors,
        tweet_text=tweet_text,
        tweet_username=tweet_username,
    )
    tweet_ownership = run_instructor_query(
        system_prompt, user_prompt, llm_model=model, process_id="assess_tweet_ownership"
    )
    return tweet_ownership


def assess_llm_relevance(
    tweet_text: str, model: str = "gpt-4o-mini"
) -> po.TweetRelevanceInfo:
    """Assess if a tweet is related to LLMs and extract any arxiv code if present."""
    relevance_info = run_instructor_query(
        ps.LLM_TWEET_RELEVANCE_SYSTEM_PROMPT,
        ps.LLM_TWEET_RELEVANCE_USER_PROMPT.format(tweet_text=tweet_text),
        llm_model=model,
        model=po.TweetRelevanceInfo,
        process_id="assess_llm_relevance",
    )

    return relevance_info


def generate_paper_punchline(
    paper_title: str,
    notes: str,
    model: str = "claude-3-5-sonnet-20241022",
) -> str:
    """Generate a single-sentence punchline summary that captures the main finding or contribution of the paper."""
    punchline = run_instructor_query(
        ps.PUNCHLINE_SUMMARY_SYSTEM_PROMPT.format(paper_title=paper_title),
        ps.PUNCHLINE_SUMMARY_USER_PROMPT.format(notes=notes),
        llm_model=model,
        process_id="generate_paper_punchline",
    )

    if "<punchline>" in punchline:
        punchline = punchline.split("<punchline>")[1].split("</punchline>")[0]

    return punchline.strip()


def analyze_paper_images(
    arxiv_code: str,
    model: str = "claude-3-5-sonnet-20241022",
    paper_comment: Optional[str] = None,
) -> str:
    """Analyze paper images using Claude vision API to select the most suitable one for social media."""
    # Get paper details
    ##ToDo: Move out of this script.
    paper_details = paper_db.get_extended_content(arxiv_code)
    if paper_details.empty:
        return None

    # Get paper markdown and images
    ##ToDo: Move out of this script.
    markdown_content, success = au.get_paper_markdown(arxiv_code)
    if not success:
        return None

    # Extract image filenames from markdown
    image_urls = re.findall(r"!\[.*?\]\((.*?)\)", markdown_content)
    if not image_urls:
        return None

    # Download images and convert to base64
    base64_images = []
    for url in image_urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                b64_image = base64.b64encode(response.content).decode("utf-8")
                base64_images.append(b64_image)
        except Exception as e:
            print(f"Failed to download image {url}: {str(e)}")
            continue

    if not base64_images:
        return None

    # Prepare paper summary
    paper_summary = f"""Title: {paper_details['title'].iloc[0]}
Summary: {paper_details['summary'].iloc[0]}"""

    if paper_comment:
        paper_summary += f"\n\nKey Point to Illustrate: {paper_comment}"

    # Prepare image descriptions
    image_descriptions = []
    for i, url in enumerate(image_urls, 1):
        filename = url.split("/")[-1]
        image_descriptions.append(f"Image {i}: {filename}")
    image_descriptions = "\n".join(image_descriptions)

    # Format messages using the new helper function
    messages = format_vision_messages(
        images=base64_images,
        text=ps.IMAGE_ANALYSIS_USER_PROMPT.format(
            paper_summary=paper_summary,
            image_descriptions=image_descriptions
        ),
        model=model,
        system_message=ps.IMAGE_ANALYSIS_SYSTEM_PROMPT
    )

    response = run_instructor_query(
        system_message="",  # Not used when messages provided
        user_message="",    # Not used when messages provided
        llm_model=model,
        model=po.ImageAnalysis,
        process_id="analyze_paper_images",
        messages=messages,
    )

    if not response or response.selected_image == "NA":
        return None

    try:
        selected_idx = int(response.selected_image.split()[-1]) - 1
        # Extract just the filename from the full S3 URL
        return image_urls[selected_idx].split("/")[-1]
    except:
        return None


def generate_llm_question(
    recent_discussions: str,
    model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.9,
) -> po.GeneratedQuestion:
    """Generate an intriguing question about LLMs based on recent social media discussions."""
    question_obj = run_instructor_query(
        ps.TWEET_SYSTEM_PROMPT,
        ps.TWEET_QUESTION_USER_PROMPT.format(
            recent_discussions=recent_discussions,
            base_style=ps.TWEET_BASE_STYLE,
        ),
        model=po.GeneratedQuestion,
        llm_model=model,
        temperature=temperature,
        process_id="generate_llm_question",
    )

    return question_obj


def analyze_tweet_patterns(
    tweets_text: str,
    previous_entries: str,
    model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.7,
    start_date: str = None,
    end_date: str = None,
) -> Tuple[str, str]:
    """Analyze patterns and insights from a collection of tweets."""
    response = run_instructor_query(
        ps.TWEET_ANALYSIS_SYSTEM_PROMPT,
        ps.TWEET_ANALYSIS_USER_PROMPT.format(
            tweets=tweets_text,
            start_date=start_date,
            end_date=end_date,
            previous_entries=previous_entries
        ),
        llm_model=model,
        temperature=temperature,
        process_id="analyze_tweet_patterns",
    )

    ## Extract the response from the XML elements from the string
    thinking_process = response.split("<think>")[1].split("</think>")[0]
    response = response.split("<response>")[1].split("</response>")[0]
    
    return thinking_process, response
