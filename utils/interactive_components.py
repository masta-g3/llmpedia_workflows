import json
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path
import utils.data_cards as dc
from utils.logging_utils import setup_logger

logger = setup_logger(__name__, "interactive_components.log")

def generate_simple_chart_html(parameters: Dict[str, Any], chart_type: str) -> str:
    """Generate simple HTML chart visualization."""
    
    if chart_type == "theme":
        return f"""
        <div class="theme-visualization">
            <h4>{parameters.get('theme_title', 'Theme')}</h4>
            <p>{parameters.get('theme_content', '')}</p>
            <div class="viz-container">
                <p><strong>Visualization:</strong> {parameters.get('visualization_type', 'bar')} chart</p>
                <ul>
                    {' '.join([f"<li>{item.get('label', '')}: {item.get('value', 0)}</li>" for item in parameters.get('visualization_data', [])])}
                </ul>
            </div>
            <div class="papers-list">
                <p><strong>Related Papers:</strong></p>
                <ul>
                    {' '.join([f"<li>{paper.get('title', paper.get('arxiv_code', ''))} ({paper.get('arxiv_code', '')})</li>" for paper in parameters.get('papers', [])])}
                </ul>
            </div>
            <div class="insights">
                <p><strong>Insights:</strong> {parameters.get('insights', '')}</p>
            </div>
        </div>
        """
    
    elif chart_type == "controversy":
        return f"""
        <div class="controversy-visualization">
            <h4>{parameters.get('controversy_title', 'Controversy')}</h4>
            <p>{parameters.get('controversy_content', '')}</p>
            <div class="opposing-sides">
                {' '.join([f"<div class='side'><h5>{side.get('side', '')}</h5><p>{side.get('position', '')}</p><p>Papers: {side.get('papers_count', 0)}</p></div>" for side in parameters.get('opposing_sides', [])])}
            </div>
        </div>
        """
    
    elif chart_type == "trends":
        data_points = parameters.get('data', [])
        chart_html = f"""
        <div class="trends-visualization">
            <h4>Weekly Publication Trends</h4>
            <div class="chart-container">
                <table border="1" style="width:100%; border-collapse: collapse;">
                    <tr><th>Week</th><th>Papers Published</th></tr>
                    {' '.join([f"<tr><td>{point.get('x_value', '')}</td><td>{point.get('y_value1', 0)}</td></tr>" for point in data_points])}
                </table>
            </div>
        </div>
        """
        return chart_html
    
    return f"<div>Chart type '{chart_type}' not supported</div>"

def generate_data_card_for_theme(theme_data: Dict[str, Any], visualization_spec: Dict[str, Any]) -> str:
    """Generate a data card HTML for a theme panel."""
    
    # Load the theme panel component
    component_path = Path(__file__).parent / "data_cards" / "components" / "theme_panel_v1.json"
    
    try:
        with open(component_path, 'r') as f:
            component_def = json.load(f)
        
        # Prepare the parameters for the theme panel
        parameters = {
            "theme_title": theme_data.get('title', 'Theme'),
            "theme_content": theme_data.get('content', ''),
            "visualization_data": visualization_spec.get('data', []),
            "visualization_type": visualization_spec.get('type', 'bar'),
            "papers": [
                {
                    "arxiv_code": paper_id,
                    "title": f"Paper {paper_id}",  # This would need to be looked up from the database
                    "summary": "Summary not available"
                }
                for paper_id in theme_data.get('papers', [])
            ],
            "concepts": theme_data.get('concepts', []),
            "insights": visualization_spec.get('insights', '')
        }
        
        # Generate simple HTML visualization
        html_content = generate_simple_chart_html(parameters, "theme")
        
        logger.info(f"Generated data card for theme: {theme_data.get('title', 'Unknown')}")
        return html_content
        
    except Exception as e:
        logger.error(f"Failed to generate data card for theme: {e}")
        return f"<div class='error'>Failed to generate visualization for theme: {theme_data.get('title', 'Unknown')}</div>"

def generate_data_card_for_controversy(controversy_data: Dict[str, Any], visualization_spec: Dict[str, Any]) -> str:
    """Generate a data card HTML for a controversy visualization."""
    
    component_path = Path(__file__).parent / "data_cards" / "components" / "controversy_view_v1.json"
    
    try:
        with open(component_path, 'r') as f:
            component_def = json.load(f)
        
        # Prepare parameters for controversy view
        parameters = {
            "controversy_title": controversy_data.get('title', 'Research Controversy'),
            "controversy_content": controversy_data.get('content', ''),
            "opposing_sides": [
                {
                    "side": side.get('side', f'Side {i+1}'),
                    "position": side.get('position', 'Position not specified'),
                    "papers": side.get('papers', []),
                    "papers_count": len(side.get('papers', [])),
                    "strength": 50 + (i * 25)  # Mock strength values
                }
                for i, side in enumerate(controversy_data.get('opposing_papers', []))
            ],
            "spectrum_data": visualization_spec.get('data', []),
            "community_sentiment": {
                "side_a_support": 40,
                "side_b_support": 45,
                "neutral_undecided": 15
            }
        }
        
        html_content = generate_simple_chart_html(parameters, "controversy")
        
        logger.info(f"Generated data card for controversy: {controversy_data.get('title', 'Unknown')}")
        return html_content
        
    except Exception as e:
        logger.error(f"Failed to generate data card for controversy: {e}")
        return f"<div class='error'>Failed to generate controversy visualization</div>"

def generate_trends_chart(trends_data: Dict[str, Any], weekly_counts: Dict[str, int]) -> str:
    """Generate a trends chart using the existing line chart component."""
    
    component_path = Path(__file__).parent / "data_cards" / "components" / "line_chart_v1.json"
    
    try:
        with open(component_path, 'r') as f:
            component_def = json.load(f)
        
        # Convert weekly_counts to chart data format
        sorted_weeks = sorted(weekly_counts.items(), key=lambda x: pd.to_datetime(x[0]))
        
        chart_data = []
        for date_str, count in sorted_weeks:
            date_dt = pd.to_datetime(date_str)
            formatted_date = date_dt.strftime("%b %d")
            chart_data.append({
                "x_value": formatted_date,
                "y_value1": count,
                "y_value1_name": "Papers Published"
            })
        
        parameters = {
            "data": chart_data,
            "y_axis_label": "Number of Papers",
            "x_axis_label": "Week"
        }
        
        html_content = generate_simple_chart_html(parameters, "trends")
        
        logger.info("Generated trends chart")
        return html_content
        
    except Exception as e:
        logger.error(f"Failed to generate trends chart: {e}")
        return "<div class='error'>Failed to generate trends chart</div>"

def assemble_interactive_report_html(
    structured_content: Dict[str, Any], 
    interactive_components: Dict[str, Any],
    weekly_counts: Dict[str, int]
) -> str:
    """Assemble all components into a complete interactive HTML report."""
    
    html_parts = []
    
    # Header
    html_parts.append("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Interactive Weekly Review - LLMpedia</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { text-align: center; margin-bottom: 40px; }
            .section { margin-bottom: 30px; }
            .theme-panel { margin-bottom: 25px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
            .theme-header { background: #b31b1b; color: white; padding: 15px; font-weight: bold; }
            .theme-content { padding: 15px; }
            .controversy-section { border: 2px solid #b31b1b; border-radius: 8px; margin-top: 30px; }
        </style>
    </head>
    <body>
    """)
    
    # Title and intro
    html_parts.append(f"""
    <div class="header">
        <h1>Interactive Weekly Review</h1>
        <p>{structured_content.get('intro', {}).get('content', 'Weekly review content not available')}</p>
    </div>
    """)
    
    # Trends section
    html_parts.append('<div class="section">')
    html_parts.append('<h2>Publication Trends</h2>')
    trends_chart = generate_trends_chart(
        structured_content.get('intro', {}).get('trends_data', {}),
        weekly_counts
    )
    html_parts.append(trends_chart)
    html_parts.append('</div>')
    
    # Theme sections
    html_parts.append('<div class="section">')
    html_parts.append('<h2>Research Themes</h2>')
    
    for theme_component in interactive_components.get('themes', []):
        theme_data = theme_component.get('theme_data', {})
        viz_spec = theme_component.get('visualization', {})
        
        html_parts.append('<div class="theme-panel">')
        html_parts.append(f'<div class="theme-header">{theme_data.get("title", "Theme")}</div>')
        html_parts.append('<div class="theme-content">')
        
        # Add theme content
        html_parts.append(f'<p>{theme_data.get("content", "")}</p>')
        
        # Add visualization
        theme_card = generate_data_card_for_theme(theme_data, viz_spec)
        html_parts.append(theme_card)
        
        html_parts.append('</div>')
        html_parts.append('</div>')
    
    html_parts.append('</div>')
    
    # Controversy section
    if interactive_components.get('controversy'):
        controversy_data = structured_content.get('controversy', {})
        controversy_viz = interactive_components.get('controversy', {})
        
        html_parts.append('<div class="controversy-section">')
        html_parts.append(f'<h2>{controversy_data.get("title", "Research Controversy")}</h2>')
        html_parts.append(f'<p>{controversy_data.get("content", "")}</p>')
        
        controversy_card = generate_data_card_for_controversy(controversy_data, controversy_viz)
        html_parts.append(controversy_card)
        
        html_parts.append('</div>')
    
    # Footer
    html_parts.append("""
    <footer style="margin-top: 50px; text-align: center; color: #666;">
        <p>Generated by LLMpedia Interactive Weekly Review System</p>
    </footer>
    </body>
    </html>
    """)
    
    complete_html = '\n'.join(html_parts)
    logger.info("Assembled complete interactive report HTML")
    return complete_html

def save_interactive_report_html(html_content: str, output_path: str) -> None:
    """Save the interactive report HTML to a file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Saved interactive report to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save interactive report: {e}")
        raise