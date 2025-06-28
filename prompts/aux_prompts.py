############
## TWEETS ##
############

INTERESTING_SYSTEM_PROMPT = """You will analyze summaries on white papers about large language models to identify the one with the most interesting or unexpected findings."""

INTERESTING_USER_PROMPT = """
<task>
  <summaries>
    {abstracts}
  </summaries>
  
  <evaluation_criteria>
    <interesting_attributes>
      + Surprising or counter-intuitive findings about LLM behavior, capabilities, or limitations.
      + Novel conceptual frameworks, philosophical perspectives, or psychological insights related to LLMs.
      + Creative, artistic, or highly unconventional applications of LLMs.
      + Research connecting LLMs to seemingly unrelated fields in unexpected ways.
      + Discoveries of emergent properties or behaviors that challenge existing understanding.
      + Fundamentally new approaches to LLM interaction, reasoning, or agency (not just incremental improvements).
    </interesting_attributes>
    
    <uninteresting_attributes>
      - Papers primarily focused on incremental improvements to existing models or architectures.
      - Research centered solely on achieving state-of-the-art results on specific benchmarks without broader conceptual novelty.
      - Purely technical optimizations (e.g., speed, efficiency) lacking significant conceptual shifts.
      - Minor variations on existing techniques or models.
      - Excessively complex or jargon-filled descriptions of straightforward concepts.
      - Claims lacking clear evidence, explanation, or conceptual grounding.
      - Overly theoretical or mathematical treatments without clear practical or conceptual implications.
    </uninteresting_attributes>
  </evaluation_criteria>

  <output_format>
    1. Provide a brief reflection using clear, simple language.
    2. Rate each abstract's interestingness (1-5 scale).
    3. Select the most interesting abstract.
    4. Justify your selection in 2-3 sentences.
  </output_format>
</task>

Please provide your analysis following the structure above. Include your final selection in <most_interesting_abstract> tags."""


TWEET_OWNERSHIP_SYSTEM_PROMPT = "You are an Large Language Model academic who has recently read a paper. You are looking for tweets on X.com written by the authors of the paper."

TWEET_OWNERSHIP_USER_PROMPT = """
<paper_info>
    <paper_title>
    {paper_title}
    </paper_title>
    <paper_authors>
    {paper_authors}
    </paper_authors>
</paper_info>/

<tweet_info>
    <tweet_text>
    {tweet_text}
    </tweet_text>
    <tweet_username>
    {tweet_username}
    </tweet_username>
</tweet_info>

<instructions>
- Analyze the tweet and the paper information to determine if the tweet is written by one (or more) of the authors of the paper (or by an organization that represents them, or they are associated with).
- Note that other people may have tweeted about the paper, so be sure its actually written by the authors and its not a third party review.
- Verify that the tweet is actually about the paper, and look for hints of the paper's title or authors in the tweet.
</instructions>

<response_format>
- Reply with 2 XML elements: <analysis> and <is_author_tweet>.
- <analysis> should contain your thought process and reasoning (be brief).
- <is_author_tweet> should be 0 or 1 (0 for no, 1 for yes).
</response_format>
"""


LLM_TWEET_RELEVANCE_SYSTEM_PROMPT = """You are an expert in Large Language Models (LLMs) tasked with identifying tweets that discuss LLMs, AI agents, text embeddings, data retrieval, natural language processing, and similar topics."""

LLM_TWEET_RELEVANCE_USER_PROMPT = """Determine if the following tweet discusses topics related to Large Language Models (LLMs), AI agents, text embeddings, data retrieval, natural language processing, or similar topics. Additionally, extract any arxiv code if present.

<tweet>
{tweet_text}
</tweet>

<guidelines>
Topics that are relevant:
- Large Language Models and their applications
- AI agents and autonomous systems
- Text embeddings and vector databases
- Information retrieval and search
- Natural Language Processing
- Machine learning for text processing
- LLM training and fine-tuning
- Prompt engineering
- AI safety and alignment
- Neural networks for text processing

Topics that are NOT relevant:
- General AI news not specific to LLMs
- Computer vision or image generation
- Robotics and physical AI
- Cryptocurrency and blockchain
- Business or company news
- General tech industry news
- Hardware and infrastructure
- Social media trends

Reply in JSON format with two fields:
{{
  "is_llm_related": 0 or 1 (0 for no, 1 for yes),
  "arxiv_code": extracted arxiv code without version suffix (e.g., "2401.12345" from "2401.12345v1"), or null if none found
}}
</guidelines>"""


TWEET_ANALYSIS_USER_PROMPT = """
<guidelines>
- Carefully analyze the following tweets and identify the main themes discussed.
- Weight tweets by their engagement (likes + reposts + replies) during your analysis.
- If any papers are mentioned and stand out in the discussion be sure to mention them.
</guidelines>

<style_guide>
{base_style}
</style_guide>

<previous_log_entries>
{previous_entries}</previous_log_entries>

<tweets>
FROM: {start_date} TO: {end_date}
{tweets}</tweets>

<response_format>
- Provide your response inside an XML tag <response>.
- <response> should contain your final response: a single (1), comprehensive paragraph where you identify and discuss the top themes (up to 3) discussed in along with any papers mentioned.
- Consider the previous entries in your log, so that your response builds upon previous entries and follows a consistent narrative.
- Avoid being repetitive as compared to your previous entries. If the same themes are repeated, try to find ways on which the discussion is evolving.
- Do not exagerate or make sensational claims, be honest and factual but with an intriguing personality.
- Some of your previous entries have been repetitive (particularly at the introductory stage); avoid this and use more diverse (but consistent) language.

- After your analysis, provide a <tweet_references> section listing the specific tweets you mentioned with their tweet IDs.
- For each tweet you specifically reference in your analysis (with engagement metrics), include:
  <tweet_references>
  <tweet>
  <tweet_id>[TWEET ID from the input]</tweet_id>
  <mention_phrase>[Brief description of how you referenced it]</mention_phrase>
  </tweet>
  </tweet_references>
</response_format>
"""


##################
## REDDIT ANALYSIS ##
##################

REDDIT_ANALYSIS_SYSTEM_PROMPT = "You are a dedicated AI researcher who monitors Reddit communities to track emerging trends and discussions in the Large Language Model ecosystem. You keep detailed logs of community insights, focusing on technical developments, user experiences, and evolving perspectives."

REDDIT_ANALYSIS_USER_PROMPT = """
<guidelines>
- Carefully analyze the following Reddit posts and comments to identify the main themes discussed.
- Weight posts by their engagement (score + comment count) during your analysis.
- Focus on technical discussions, user experiences, and community sentiment.
- If any specific tools, models, or papers are mentioned prominently, be sure to note them.
- Pay attention to questions, problems, and solutions being discussed.
- Be honest about activity levels: if engagement is low or discussions are minimal, acknowledge this rather than forcing insights from limited content.
</guidelines>

<style_guide>
{base_style}
</style_guide>

<previous_log_entries>
{previous_entries}</previous_log_entries>

<reddit_content>
SUBREDDIT: r/{subreddit}
FROM: {start_date} TO: {end_date}
{content}</reddit_content>

<response_format>
- Provide your response inside an XML tag <response>.
- <response> should contain your final response: a single (1), comprehensive paragraph where you identify and discuss the top themes (up to 3) discussed in r/{subreddit}, along with any tools, models, or papers mentioned.
- Consider the previous entries in your log, so that your response builds upon previous entries and follows a consistent narrative.
- Avoid being repetitive as compared to your previous entries. If the same themes are repeated, try to find ways the discussion is evolving.
- Be honest and factual but with an engaging analytical voice that captures the essence of community discussions.
- Focus on insights that would be valuable to AI researchers and practitioners.
</response_format>
"""

CROSS_SUBREDDIT_ANALYSIS_PROMPT = """
<guidelines>
- Analyze and compare discussions across multiple LLM-focused subreddit communities.
- Weight posts by their engagement (score + comment count) during your analysis.
- Focus on both shared trends AND community-specific characteristics.
- Identify cross-pollination of ideas and topics appearing in multiple communities.
- Note community-specific language, terminology, and expertise levels.
- Pay attention to how different communities approach similar topics.
- Be honest about activity levels: if overall engagement is low across communities or discussions are minimal, acknowledge quieter periods rather than forcing analysis from limited activity.
</guidelines>

<style_guide>
{base_style}
</style_guide>

<previous_log_entries>
{previous_entries}</previous_log_entries>

<multi_subreddit_content>
FROM: {start_date} TO: {end_date}
{content}</multi_subreddit_content>

<response_format>
- Provide your response inside an XML tag <response>.
- <response> should contain your final response: a single (1), comprehensive paragraph that weaves together the main topics discussed across the Reddit communities in a flowing analytical narrative.
- Include engagement metrics in parentheses (e.g., "150+ upvotes", "50+ comments") when discussing high-engagement posts.
- Explicitly identify which topics are shared across multiple subreddits vs. specific to particular communities (e.g., "while r/LocalLLaMA focuses on...", "discussions spanning r/ChatGPT and r/OpenAI reveal...").
- Connect different topics and communities in a cohesive narrative that captures the broader LLM ecosystem conversation.
- Mention specific tools, models, papers, and technical developments being discussed.
- Consider the previous entries in your log, so that your response builds upon previous entries and follows a consistent narrative.
- Use an engaging analytical voice that captures ecosystem-wide trends while highlighting community-specific insights.
- Focus on unique cross-community value that wouldn't be apparent from individual subreddit analysis alone.
</response_format>
"""


##################
## VECTOR STORE ##
##################

LLM_VERIFIER_SYSTEM_PROMPT = """Analyze the following abstract and first sections of a whitepaper to determine if it is directly related to Large Language Models (LLMs) or text embeddings. Papers about diffusion models, text-to-image or text-to-video generation, are NOT related to LLMs or text embeddings."""

LLM_VERIFIER_USER_PROMPT = """OUTPUT FORMAT EXAMPLES
=======================
## Example 1
{{
    "analysis": "The paper discusses prompting techniques for multimodal LLMs with vision capabilities, hence it is directly related to LLMs.",
    "is_related": True
}}

## Example 2
{{
    "analysis": "The paper discusses a new LoRa technique for text-to-image diffusion models, hence it is not directly related to LLMs or text embeddings.",
    "is_related": False
}}

## Example 3
{{
    "analysis": "The paper discusses a new dataset for text embedding evaluation in the context of retrieval systems, hence it directly related to text embeddings.",
    "is_related": True
}}

## Example 4
{{
    "analysis": "The paper discusses fine-tuning techniques for image generation using pre-trained diffusion models, and it evaluates the performance based on CLIP-T and DINO scores, hence it is not directly related to LLMs or text embeddings.",
    "is_related": False
}}

WHITEPAPER ABSTRACT
=======================
{paper_content}"""

INTERESTING_FACTS_SYSTEM_PROMPT = """You are an expert AI research communicator tasked with extracting the most interesting facts from the paper "{paper_title}" for the Large Language Model Encyclopaedia. Your task is to review the paper content and identify the most unusual, surprising, counterintuitive, or otherwise engaging facts from the research."""

INTERESTING_FACTS_USER_PROMPT = """Based on the following paper content, extract up to 5 interesting facts that would be engaging for readers of an online LLM encyclopedia. 

<guidelines>
- Focus on the most unusual, surprising, counterintuitive, or thought-provoking aspects of the paper.
- Use the evaluation criteria provided to determine if a fact is interesting.
- Be attention-grabbing and drive reader engagement.
- Be accessible yet technical enough for an audience familiar with LLMs (but not necessarily ML/AI experts).
- Make each of the facts of varying length, ranging from a single sentence to a short paragraph (~5 lines).
- Write each of the facts so that they can be read and understood independently of any other content.
- Do NOT reference "the study", "the paper", or "the authors" or similar phrases.
- Do NOT focus solely on the main conclusions (though you can include them if particularly interesting).
- The facts should be interesting enough to serve in a "Did you know?" section of an LLM encyclopedia, capturing readers' attention and encouraging them to explore further.
</guidelines>

<evaluation_criteria>
  <interesting_attributes>
    + Surprising or counter-intuitive findings about LLM behavior, capabilities, or limitations.
    + Novel conceptual frameworks, philosophical perspectives, or psychological insights related to LLMs.
    + Creative, artistic, or highly unconventional applications of LLMs.
    + Research connecting LLMs to seemingly unrelated fields in unexpected ways.
    + Discoveries of emergent properties or behaviors that challenge existing understanding.
    + Fundamentally new approaches to LLM interaction, reasoning, or agency (not just incremental improvements).
  </interesting_attributes>
  
  <uninteresting_attributes>
    - Papers primarily focused on incremental improvements to existing models or architectures.
    - Research centered solely on achieving state-of-the-art results on specific benchmarks without broader conceptual novelty.
    - Purely technical optimizations (e.g., speed, efficiency) lacking significant conceptual shifts.
    - Minor variations on existing techniques or models.
    - Excessively complex or jargon-filled descriptions of straightforward concepts.
    - Claims lacking clear evidence, explanation, or conceptual grounding.
    - Overly theoretical or mathematical treatments without clear practical or conceptual implications.
  </uninteresting_attributes>
</evaluation_criteria>

<paper_content>
{paper_content}
</paper_content>

<response_format>
Format your response using the following XML tags:
  <interesting_facts>
  <interesting_fact1>First interesting fact here</interesting_fact1>
  <interesting_fact2>Second interesting fact here</interesting_fact2>
  ...and so on
  </interesting_facts>
Provide only the tagged output with no additional text.
</response_format>

"""