import sys, os
import pandas as pd
import json
from dotenv import load_dotenv
from typing import Dict, List, Any, Tuple

load_dotenv()

PROJECT_PATH = os.getenv("PROJECT_PATH", "/app")
sys.path.append(PROJECT_PATH)

os.chdir(PROJECT_PATH)

import utils.paper_utils as pu
import utils.vector_store as vs
import utils.db.paper_db as paper_db
import utils.db.db_utils as db_utils
import utils.db.tweet_db as tweet_db
import utils.plots as plots
import utils.data_cards as dc
import utils.interactive_components as ic
from utils.logging_utils import setup_logger
from utils.instruct import run_instructor_query
import prompts.weekly_prompts as wp

# Set up logging
logger = setup_logger(__name__, "weekly_interactive_review.log")

## Constants
DEFAULT_MODEL = "claude-3-7-sonnet-20250219"

## AUXILIARY FUNCTIONS ##

def prepare_date(date_str: str) -> tuple[str, pd.Timestamp]:
    """Converts date_str to datetime and shifts to previous Monday if needed."""
    date_str_dt = pd.to_datetime(date_str)
    days_since_monday = date_str_dt.weekday()
    if days_since_monday > 0:
        date_str_dt = date_str_dt - pd.Timedelta(days=days_since_monday)
        date_str = date_str_dt.strftime("%Y-%m-%d")
    logger.info(f"Processing interactive weekly review for week of {date_str}")
    return date_str, date_str_dt

def get_weekly_data(current_date_str: str, date_st_dt: pd.Timestamp) -> tuple[pd.DataFrame, dict, list[str]]:
    """Fetches weekly content dataframe and past weekly counts."""
    weekly_content_df = paper_db.get_weekly_summary_inputs(current_date_str)
    logger.info(f"Found {len(weekly_content_df)} papers for the week {current_date_str}")

    ## Get weekly total counts for the last 16 weeks.
    prev_mondays_dt_range = pd.date_range(
        date_st_dt - pd.Timedelta(days=7 * 16), date_st_dt, freq="W-MON"
    )
    prev_mondays_str_list = [date.strftime("%Y-%m-%d") for date in prev_mondays_dt_range]
    weekly_counts = {
        d_str: len(paper_db.get_weekly_summary_inputs(d_str))
        for d_str in prev_mondays_str_list
    }
    logger.info("Retrieved weekly counts for the past 16 weeks")
    return weekly_content_df, weekly_counts, prev_mondays_str_list

def get_previous_themes_str(prev_mondays_str_list: list[str]) -> str:
    """Retrieves themes from previous weeks' summaries."""
    try:
        previous_summaries = []
        for i in range(2, 6): 
            if len(prev_mondays_str_list) > i:
                summary = paper_db.get_weekly_content(
                    prev_mondays_str_list[-i], content_type="content"
                )
                if summary:
                    previous_summaries.append(summary)
        
        if previous_summaries:
            previous_themes = "\n".join([s.split("\n")[0] for s in previous_summaries if s])
            logger.info(f"Retrieved {len(previous_summaries)} previous weeks' themes")
        else:
            previous_themes = "N/A"
            logger.info("No previous themes found or previous summaries were empty.")

    except Exception as e:
        logger.warning(f"Could not retrieve previous themes due to: {e}. Falling back to old method.")
        if len(prev_mondays_str_list) > 1:
            previous_summary_old = paper_db.get_weekly_summary_old(prev_mondays_str_list[-2])
            if previous_summary_old is None:
                previous_themes = "N/A"
                logger.warning("Could not find previous week's summary using old method either.")
            else:
                split_summary = previous_summary_old.split("\n##")
                if len(split_summary) > 2:
                    previous_themes = split_summary[2]
                else:
                    previous_themes = previous_summary_old
                logger.info("Retrieved previous week's summary themes from old format")
        else:
            previous_themes = "N/A"
            logger.warning("Not enough past Mondays to fetch previous themes.")
            
    return previous_themes

def format_content_for_llm(weekly_content_df: pd.DataFrame, weekly_counts: dict) -> str:
    """Formats the weekly content data for LLM processing."""
    md_content = "## Weekly Publication Trends\n"
    md_content += "| Week | Total Papers |\n"
    md_content += "| --- | --- |\n"
    
    sorted_weekly_counts = sorted(weekly_counts.items(), key=lambda item: pd.to_datetime(item[0]))
    
    for tmp_date_str, count in sorted_weekly_counts:
        iter_date_dt = pd.to_datetime(tmp_date_str)
        iter_date_st_long_str = iter_date_dt.strftime("%B %d, %Y")
        iter_date_end_dt = iter_date_dt + pd.Timedelta(days=6)
        iter_date_end_long_str = iter_date_end_dt.strftime("%B %d, %Y")
        md_content += f"| {iter_date_st_long_str} to {iter_date_end_long_str} | {count} |\n"
    md_content += "\n\n"

    md_content += "## Papers Published This Week\n"
    for _, row in weekly_content_df.iterrows():
        paper_markdown = pu.format_paper_summary(row)
        md_content += paper_markdown
            
    logger.info("Formatted weekly content for LLM")
    return md_content

def generate_structured_weekly_content(
    weekly_content_df: pd.DataFrame, 
    weekly_counts: dict, 
    previous_themes_text: str,
    tweet_analysis_markdown_text: str
) -> Dict[str, Any]:
    """Generate structured content that includes theme metadata and visualization hints."""
    
    STRUCTURED_WEEKLY_PROMPT = """
    Generate a weekly report with the following JSON structure. Make sure to follow the exact format:
    
    {
      "intro": {
        "content": "Introduction paragraph text discussing publication volume trends and main themes...",
        "trends_data": {
          "volume_observation": "Brief observation about publication volume patterns",
          "main_themes": ["theme1", "theme2", "theme3"]
        }
      },
      "themes": [
        {
          "title": "Theme Title",
          "content": "Theme paragraph content...",
          "papers": ["arxiv:1234.5678", "arxiv:2345.6789"],
          "concepts": ["concept1", "concept2"],
          "chart_specification": {
            "type": "bar|scatter|line|grouped_bar|stacked_bar|radar|network",
            "visualization_mode": "conceptual|quantitative", 
            "data_structure": {
              "x_axis_items": ["item1", "item2", "item3"],
              "y_axis_concept": "performance|effectiveness|ranking|count",
              "categories": ["category1", "category2"] // optional for grouped/stacked charts
            },
            "visual_story": "Brief description of what this chart should convey",
            "axis_labels": {
              "x": "X axis label",
              "y": "Y axis label"
            },
            "title_suffix": "suffix for chart title" // optional
          }
        }
      ],
      "controversy": {
        "title": "Controversy Title", 
        "content": "Controversy content...",
        "opposing_papers": [
          {"side": "A", "papers": ["arxiv:1111.2222"], "position": "position description"},
          {"side": "B", "papers": ["arxiv:3333.4444"], "position": "position description"}
        ]
      }
    }
    
    IMPORTANT: Generate intelligent chart specifications:
    
    1. VISUALIZATION_MODE:
    - Use "quantitative" ONLY when specific numbers are mentioned in content
    - Use "conceptual" for general relationships without specific data
    
    2. CHART_TYPE Selection based on content:
    - "bar": Compare discrete items/methods (most common)
    - "grouped_bar": Compare items across multiple dimensions
    - "scatter": Show relationships between two variables
    - "line": Show trends/progression over time
    - "stacked_bar": Show composition/parts of whole
    - "radar": Compare items across multiple criteria
    - "network": Show relationships/connections between concepts
    
    3. DATA_STRUCTURE should reflect what you want to compare:
    - x_axis_items: The main things being compared (models, methods, approaches)
    - y_axis_concept: What metric/quality is being measured
    - categories: For grouped charts, what dimensions to show
    
    4. VISUAL_STORY: One sentence explaining what insight the chart reveals
    
    Examples:
    - Content: "GPT-4o outperformed Claude across reasoning tasks"
      → type: "bar", x_axis_items: ["GPT-4o", "Claude"], y_axis_concept: "performance"
    - Content: "Three optimization methods showed different speed-accuracy tradeoffs" 
      → type: "scatter", x_axis_items: ["Method A", "B", "C"], y_axis_concept: "efficiency_ranking"
    
    {style_guidelines}
    
    <content>
    {weekly_content}
    </content>
    
    <tweet_discussions>
    {tweet_analysis}
    </tweet_discussions>
    
    <previous_themes>
    {previous_themes}
    </previous_themes>
    
    Important: Return only the JSON object, no other text or explanations.
    """
    
    weekly_content_formatted = format_content_for_llm(weekly_content_df, weekly_counts)
    
    prompt = STRUCTURED_WEEKLY_PROMPT.format(
        style_guidelines=wp.WEEKLY_USER_PROMPT.split('<content>')[0],
        weekly_content=weekly_content_formatted,
        tweet_analysis=tweet_analysis_markdown_text,
        previous_themes=previous_themes_text
    )
    
    logger.info("Generating structured content using LLM")
    
    try:
        response = run_instructor_query(
            system_message=wp.WEEKLY_SYSTEM_PROMPT,
            user_message=prompt,
            llm_model=DEFAULT_MODEL,
            temperature=1,
            max_tokens=50000,
            process_id="generate_structured_weekly_content"
        )
        
        logger.info(f"Raw LLM response: {response[:500]}...")  # Log first 500 chars for debugging
        
        # Clean response and parse JSON
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        
        # Additional cleaning - remove any extra whitespace and newlines at start/end
        response = response.strip()
        
        # Try to find JSON content if wrapped in other text
        if '{' in response and '}' in response:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            response = response[start_idx:end_idx]
        
        logger.info(f"Cleaned JSON response: {response[:200]}...")  # Log cleaned version
        
        structured_content = json.loads(response)
        logger.info("Successfully generated structured content")
        return structured_content
        
    except json.JSONDecodeError as je:
        logger.error(f"JSON decode error: {je}")
        logger.error(f"Problematic response: {response}")
        # Fallback to basic structure
        return {
            "intro": {
                "content": f"Failed to parse JSON response: {str(je)[:100]}",
                "trends_data": {
                    "volume_observation": "JSON parsing failed",
                    "main_themes": ["General ML Research"]
                }
            },
            "themes": [],
            "controversy": None
        }
    except Exception as e:
        logger.error(f"Failed to generate structured content: {e}")
        logger.error(f"Response that caused error: {response if 'response' in locals() else 'No response'}")
        # Fallback to basic structure
        return {
            "intro": {
                "content": f"Failed to generate structured content: {str(e)[:100]}",
                "trends_data": {
                    "volume_observation": "Content generation failed",
                    "main_themes": ["General ML Research"]
                }
            },
            "themes": [],
            "controversy": None
        }

def generate_trend_visualization(trends_data: Dict[str, Any], weekly_counts: dict) -> Dict[str, Any]:
    """Generate visualization specification for publication trends."""
    
    # Convert weekly_counts to DataFrame for plotting
    trend_df = pd.DataFrame([
        {"date": date_str, "count": count} 
        for date_str, count in weekly_counts.items()
    ])
    trend_df["date"] = pd.to_datetime(trend_df["date"])
    trend_df = trend_df.sort_values("date")
    
    # Generate Plotly specification
    viz_spec = {
        "type": "line_chart",
        "data": trend_df.to_dict('records'),
        "config": {
            "x_axis": "date",
            "y_axis": "count",
            "title": "Weekly Publication Trends (Last 16 Weeks)",
            "color": "#b31b1b"
        },
        "insights": trends_data.get("volume_observation", "")
    }
    
    logger.info("Generated trend visualization specification")
    return viz_spec

def generate_theme_visualization_with_guidance(theme_data: Dict[str, Any], papers_data: pd.DataFrame) -> Dict[str, Any]:
    """Generate visualization with guidance from theme metadata."""
    
    suggested_viz = theme_data.get('metrics_suggested', {}).get('visualization_type', 'bar')
    
    VIZ_PROMPT = """
    Generate a JSON specification for a {viz_type} visualization for this theme using simple data structures.
    
    THEME: {title}
    SUGGESTED METRICS: {metrics}
    COMPARISON AXIS: {axis}
    CONCEPTS: {concepts}
    
    Return a JSON object with this structure:
    {{
        "type": "{viz_type}",
        "data": [
            {{"label": "paper_title_1", "value": 85, "category": "concept1"}},
            {{"label": "paper_title_2", "value": 92, "category": "concept2"}}
        ],
        "config": {{
            "title": "visualization title",
            "x_axis": "label",
            "y_axis": "value",
            "color_by": "category"
        }},
        "insights": "Brief description of what this visualization shows"
    }}
    
    Create meaningful mock data based on the theme and papers if specific metrics aren't available.
    Return only the JSON object.
    """
    
    try:
        prompt = VIZ_PROMPT.format(
            viz_type=suggested_viz,
            title=theme_data.get('title', 'Theme'),
            metrics=theme_data.get('metrics_suggested', {}).get('key_metrics', []),
            axis=theme_data.get('metrics_suggested', {}).get('comparison_axis', 'performance'),
            concepts=theme_data.get('concepts', [])
        )
        
        response = run_instructor_query(
            system_message="You are a data visualization expert creating chart specifications.",
            user_message=prompt,
            llm_model=DEFAULT_MODEL,
            temperature=0.7,
            max_tokens=2000,
            process_id="generate_theme_visualization"
        )
        
        # Clean and parse response
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
            
        viz_spec = json.loads(response)
        logger.info(f"Generated {suggested_viz} visualization for theme: {theme_data.get('title', 'Unknown')}")
        return viz_spec
        
    except Exception as e:
        logger.warning(f"Visualization generation failed: {e}")
        return generate_simple_fallback_viz(theme_data)

def generate_simple_fallback_viz(theme_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a simple fallback visualization."""
    return {
        "type": "text",
        "data": [],
        "config": {
            "title": theme_data.get('title', 'Theme Analysis'),
            "content": theme_data.get('content', 'Theme content unavailable')
        },
        "insights": "Visualization unavailable - showing text content"
    }

def generate_controversy_visualization(controversy_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate visualization for controversy section."""
    
    if not controversy_data:
        return None
        
    opposing_sides = controversy_data.get('opposing_papers', [])
    
    viz_spec = {
        "type": "divergent_bar",
        "data": [
            {
                "side": side.get('side', f'Side {i+1}'),
                "position": side.get('position', 'Unknown position'),
                "papers_count": len(side.get('papers', [])),
                "papers": side.get('papers', [])
            }
            for i, side in enumerate(opposing_sides)
        ],
        "config": {
            "title": controversy_data.get('title', 'Research Controversy'),
            "description": controversy_data.get('content', '')
        },
        "insights": "Visualization of opposing research positions"
    }
    
    logger.info("Generated controversy visualization specification")
    return viz_spec

def generate_interactive_components(structured_content: Dict[str, Any], weekly_content_df: pd.DataFrame, weekly_counts: Dict[str, int]) -> Dict[str, Any]:
    """Generate visualizations for each section of the structured content."""
    
    components = {}
    
    # 1. Generate trend visualization
    components['trends'] = generate_trend_visualization(
        structured_content['intro']['trends_data'],
        weekly_counts
    )
    
    # 2. Generate theme visualizations (sequential)
    components['themes'] = []
    for theme in structured_content.get('themes', []):
        # Filter papers relevant to this theme
        theme_papers = theme.get('papers', [])
        filtered_papers_data = weekly_content_df[
            weekly_content_df['arxiv_code'].isin(theme_papers)
        ] if not weekly_content_df.empty else pd.DataFrame()
        
        viz_spec = generate_theme_visualization_with_guidance(
            theme_data=theme,
            papers_data=filtered_papers_data
        )
        components['themes'].append({
            'theme_data': theme,
            'visualization': viz_spec
        })
    
    # 3. Generate controversy visualization
    if structured_content.get('controversy'):
        components['controversy'] = generate_controversy_visualization(
            controversy_data=structured_content['controversy']
        )
    
    logger.info(f"Generated interactive components for {len(components)} sections")
    return components

def assemble_interactive_report(structured_content: Dict[str, Any], interactive_components: Dict[str, Any], weekly_counts: Dict[str, int]) -> Dict[str, Any]:
    """Assemble the complete interactive report."""
    
    # Generate the complete HTML report
    html_content = ic.assemble_interactive_report_html(
        structured_content, 
        interactive_components,
        weekly_counts
    )
    
    interactive_report = {
        "metadata": {
            "generated_at": pd.Timestamp.now().isoformat(),
            "content_type": "interactive_weekly_review",
            "version": "1.0"
        },
        "structured_content": structured_content,
        "interactive_components": interactive_components,
        "html_content": html_content,
        "layout_config": {
            "theme": "arxiv_red",
            "responsive": True,
            "mobile_optimized": True
        }
    }
    
    logger.info("Assembled complete interactive report")
    return interactive_report

def store_interactive_report(interactive_report: Dict[str, Any], current_date_str: str):
    """Store the interactive report to the database and save HTML file."""
    
    # Convert the interactive report to a format suitable for storage
    report_data = pd.DataFrame([{
        "content": json.dumps(interactive_report["structured_content"]),
        "interactive_components": json.dumps(interactive_report["interactive_components"]),
        "metadata": json.dumps(interactive_report["metadata"]),
        "layout_config": json.dumps(interactive_report["layout_config"]),
        "date": pd.to_datetime(current_date_str),
        "tstp": pd.Timestamp.now(),
        "content_type": "interactive_weekly_review"
    }])
    
    # Also save the HTML content as a separate file
    html_output_path = f"artifacts/interactive_weekly_review_{current_date_str}.html"
    try:
        ic.save_interactive_report_html(interactive_report["html_content"], html_output_path)
        logger.info(f"Saved HTML report to {html_output_path}")
    except Exception as e:
        logger.warning(f"Failed to save HTML file: {e}")
    
    logger.info("Storing interactive report to database")
    db_utils.upload_dataframe(report_data, "weekly_content_interactive")
    logger.info(f"Successfully stored interactive weekly review for date: {current_date_str}")

def get_tweet_analysis_markdown(date_st_dt: pd.Timestamp) -> str:
    """Fetches and formats tweet analysis for the week."""
    logger.info("Fetching tweet analysis for the week")
    week_end_dt = date_st_dt + pd.Timedelta(days=6)
    tweet_analysis_df = tweet_db.get_tweet_analysis_between(date_st_dt, week_end_dt)

    if tweet_analysis_df.empty:
        tweet_analysis_md_str = "No tweet analysis available for this week."
        logger.info("No tweet analysis found for the week.")
    else:
        tweet_analysis_md_str = "## Community Discussions\n" + "\n\n".join(
            tweet_analysis_df["response"].tolist()
        )
        logger.info(f"Formatted {tweet_analysis_df.shape[0]} tweet analysis entries.")
    return tweet_analysis_md_str

def generate_enhanced_weekly_review(date_str: str) -> Dict[str, Any]:
    """Enhanced workflow with structured content generation."""
    
    # STEP 1: Existing data collection (unchanged)
    current_date_str, date_st_dt = prepare_date(date_str)
    weekly_content_df, weekly_counts, prev_mondays_str_list = get_weekly_data(current_date_str, date_st_dt)
    
    # Get previous themes and tweet analysis
    previous_themes_text = get_previous_themes_str(prev_mondays_str_list)
    tweet_analysis_markdown_text = get_tweet_analysis_markdown(date_st_dt)
    
    # STEP 2: Enhanced content generation with structured output
    structured_content = generate_structured_weekly_content(
        weekly_content_df, weekly_counts, previous_themes_text, tweet_analysis_markdown_text
    )
    
    # STEP 3: Generate visualizations for each structured section
    interactive_components = generate_interactive_components(structured_content, weekly_content_df, weekly_counts)
    
    # STEP 4: Assemble and store
    interactive_report = assemble_interactive_report(structured_content, interactive_components, weekly_counts)
    store_interactive_report(interactive_report, current_date_str)
    
    return interactive_report

def main(date_str_input: str):
    """Generate an interactive weekly review with visualizations and structured content."""
    
    logger.info(f"Starting interactive weekly review generation for {date_str_input}")
    
    vs.validate_openai_env()
    
    current_date_str, _ = prepare_date(date_str_input)
    
    # Check if interactive review already exists
    # Note: This would need a new check function for interactive reviews
    # if paper_db.check_interactive_weekly_summary_exists(current_date_str):
    #     logger.info(f"Interactive weekly summary for {current_date_str} already exists. Skipping...")
    #     return
    
    try:
        interactive_report = generate_enhanced_weekly_review(date_str_input)
        logger.info(f"Successfully completed interactive weekly review generation for {current_date_str}")
        return interactive_report
        
    except Exception as e:
        logger.error(f"Failed to generate interactive weekly review: {e}")
        raise

if __name__ == "__main__":
    run_date_str = sys.argv[1] if len(sys.argv) == 2 else "2025-05-19"
    main(run_date_str)