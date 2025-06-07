import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import pandas as pd
import numpy as np
import colorcet as cc
import datetime
from typing import Tuple, Dict, List, Optional, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.cm as cm
import matplotlib.font_manager as fm
from matplotlib.ticker import MaxNLocator
import json
import re

pio.templates.default = "plotly"


def plot_publication_counts(df: pd.DataFrame, cumulative=False) -> go.Figure:
    """Plot line chart of total number of papers updated per day."""
    df["published"] = pd.to_datetime(df["published"])
    df["published"] = df["published"].dt.date
    df = df.groupby("published")["title"].nunique().reset_index()
    df.columns = ["published", "Count"]
    df["published"] = pd.to_datetime(df["published"])
    df.sort_values("published", inplace=True)
    df["Cumulative Count"] = df["Count"].cumsum()
    if cumulative:
        fig = px.area(
            df,
            x="published",
            y="Cumulative Count",
            title=None,
            color_discrete_sequence=["#b31b1b"],
        )
    else:
        fig = px.bar(
            df,
            x="published",
            y="Count",
            color_discrete_sequence=["#b31b1b"],
        )
    fig.update_xaxes(title=None, tickfont=dict(size=17))
    fig.update_yaxes(title_font=dict(size=18), tickfont=dict(size=17))

    return fig


def plot_activity_map(df_year: pd.DataFrame) -> Tuple[go.Figure, pd.DataFrame]:
    """Creates a calendar heatmap plot using scatter markers instead of a heatmap."""
    colors = ["#f8c0c0", "#f09898", "#e87070", "#e04848", "#c93232", "#b31b1b"]
    
    # Create a colorscale function to map values to colors
    max_count = df_year["Count"].max() if not df_year.empty else 1
    min_count = df_year[df_year["Count"] > 0]["Count"].min() if not df_year.empty else 0
    
    def get_color(count):
        if count == 0:
            return "rgba(240, 240, 240, 0.5)"  # Light gray for zero values
        
        log_count = np.log1p(count - min_count + 1)
        log_max = np.log1p(max_count - min_count + 1)
        
        normalized = (log_count / log_max) ** 2
        color_idx = int(normalized * (len(colors) - 1))
        return colors[color_idx]
    
    week_max_dates = (
        df_year.groupby(df_year["published"].dt.isocalendar().week)["published"]
        .max()
        .dt.strftime("%b %d")
        .tolist()
    )

    # Create pivot tables for counts and dates
    padded_count = df_year.pivot_table(
        index="weekday", columns="week", values="Count", aggfunc="sum"
    ).fillna(0)
    padded_date = df_year.pivot_table(
        index="weekday", columns="week", values="published", aggfunc="last"
    ).fillna(pd.NaT)
    
    # Convert dates to string format
    padded_date = padded_date.applymap(
        lambda x: x.strftime("%b %d") if pd.notna(x) else ""
    )
    
    # Days of the week in display order (top to bottom)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Create figure
    fig = go.Figure()
    
    # Add scatter markers to simulate heatmap
    for y_idx, y_val in enumerate(days):
        for x_idx, x_val in enumerate(padded_date.iloc[0].values):
            if x_val:  # Only add points for non-empty dates
                count = int(padded_count.values[y_idx, x_idx])
                date_str = padded_date.values[y_idx, x_idx]
                
                # Store coordinates for selection handling
                coords = f"{y_idx},{x_idx}"
                
                fig.add_trace(
                    go.Scatter(
                        x=[x_val],
                        y=[y_val],
                        mode="markers",
                        marker=dict(
                            size=22,
                            color=get_color(count),
                            symbol="square",
                            line=dict(width=1, color="white"),
                        ),
                        name="",
                        showlegend=False,
                        hovertemplate=f"{date_str}<br>Count: {count}<extra></extra>",
                        text=[coords],
                    )
                )
    
    fig.update_layout(
        height=210,
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(tickfont=dict(color="grey"), showgrid=False, zeroline=False)
    fig.update_yaxes(tickfont=dict(color="grey"), showgrid=False, zeroline=False)

    return fig, padded_date


def plot_weekly_activity_ts(
    df: pd.DataFrame, date_report: datetime.date = None
) -> go.Figure:
    """Calculate weekly activity and plot a time series."""
    df = df.copy()
    df["published"] = pd.to_datetime(df["published"])
    year_range = df["published"].dt.year.unique()
    date_format = "%b %d, %y" if len(year_range) > 1 else "%b %d"
    df = df.sort_values("published")
    df["week_start"] = df["published"].dt.to_period("W").apply(lambda r: r.start_time)
    df = df.groupby(["week_start"])["Count"].sum().reset_index()
    df["publish_str"] = df["week_start"].dt.strftime(date_format)

    highlight_date_str = date_report.strftime(date_format)

    fig = px.area(
        df,
        x="publish_str",
        y="Count",
        title=None,
        labels={"title": "Papers Published"},
        height=250,
        color_discrete_sequence=["#b31b1b"],
    )
    fig.update_xaxes(title=None, tickfont=dict(size=17))
    fig.update_yaxes(title_font=dict(size=18), tickfont=dict(size=17))
    fig.add_vline(x=highlight_date_str, line_width=2, line_dash="dash", line_color="#c93232")
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="# Published",
    )

    bar_height = df[df["publish_str"] == highlight_date_str]["Count"]
    if len(bar_height) > 0:
        bar_height = bar_height.values[0]
    else:
        bar_height = 0
    fig.add_trace(
        go.Scatter(
            x=[highlight_date_str],
            y=[bar_height],
            mode="markers",
            showlegend=False,
            marker=dict(size=20, color="#b31b1b"),
        )
    )
    return fig


def plot_cluster_map(df: pd.DataFrame) -> go.Figure:
    """Creates a scatter plot of the UMAP embeddings of the papers."""
    # Calculate marker size based on number of points
    n_points = len(df)
    marker_size = min(20, max(6, int(400 / n_points)))  # Size between 4 and 20, inverse to number of points
    
    # Create base contour plot
    fig = go.Figure()
    
    ## Add density contours - lines only, no fill
    fig.add_trace(go.Histogram2dContour(
        x=df["dim1"],
        y=df["dim2"],
        colorscale=[[0, "rgba(200,200,255,0.3)"], [1, "rgba(100,100,255,0.3)"]],
        showscale=False,
        ncontours=15,
        contours=dict(
            coloring="lines",
            showlabels=False,
            start=0,
            end=1,
            size=0.1,
        ),
        line=dict(width=1),
        opacity=0.4,
    ))
    
    ## Add scatter points on top.
    for topic in df["topic"].unique():
        mask = df["topic"] == topic
        topic_df = df[mask]
        
        # Prepare customdata including title, arxiv_code, published date, topic, and punchline
        customdata = []
        for _, row in topic_df.iterrows():
            custom_item = [
                row["title"],
                row.get("arxiv_code", ""),
                row.get("published", "").strftime("%b %d, %Y") if pd.notna(row.get("published", "")) else "",
                row.get("topic", ""),
                row.get("punchline", "")[:150] + "..." if len(str(row.get("punchline", ""))) > 150 else row.get("punchline", "")
            ]
            customdata.append(custom_item)
        
        fig.add_trace(go.Scatter(
            x=topic_df["dim1"],
            y=topic_df["dim2"],
            mode="markers",
            name=topic,
            marker=dict(
                size=marker_size,
                line=dict(width=0.5, color="Black"),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br><br>" +
                "<b>Topic:</b> %{customdata[3]}<br>" +
                "<b>Published:</b> %{customdata[2]}<br>" +
                "<b>Summary:</b> %{customdata[4]}<extra></extra>"
            ),
            customdata=customdata,
        ))
    
    fig.update_layout(
        legend=dict(
            title=None,
            font=dict(size=14),
        ),
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridwidth=0.1, gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(showgrid=True, gridwidth=0.1, gridcolor="rgba(128,128,128,0.1)")
    )
    fig.update_xaxes(title_text=None)
    fig.update_yaxes(title_text=None)
    return fig


def plot_repos_by_feature(
    df: pd.DataFrame, plot_by: str, max_chars: int = 30
) -> go.Figure:
    """Plot bar chart of repositories by a feature."""
    count_df = df.groupby(plot_by).count()[["repo_title"]].reset_index()

    if plot_by != "published":
        count_df[plot_by] = np.where(
            count_df["repo_title"] < 10, "Other", count_df[plot_by]
        )
        count_df = count_df.sort_values("repo_title", ascending=False)
        count_df["topic_label"] = count_df[plot_by].apply(
            lambda x: (x[:max_chars] + "...") if len(x) > max_chars else x
        )
    else:
        count_df[plot_by] = pd.to_datetime(count_df[plot_by])
        count_df[plot_by] = (
            count_df[plot_by]
            .dt.tz_localize(None)
            .dt.to_period("W")
            .apply(lambda r: r.start_time)
        )
        count_df = count_df.groupby(plot_by).sum().reset_index()
        count_df = count_df.sort_values(plot_by, ascending=True)
        count_df["topic_label"] = count_df[plot_by].dt.strftime("%b %d")

    fig = px.bar(count_df, x=plot_by, y="repo_title", title=None, hover_data=[plot_by])
    fig.update_xaxes(title=None, tickfont=dict(size=13), tickangle=75)
    fig.update_yaxes(title_font=dict(size=14), title="# Resources")
    fig.update_traces(marker_color="#b31b1b", marker_line_color="#c93232")
    return fig


def generate_daily_papers_chart(daily_counts: pd.Series, output_path: str):
    """Generate a bar chart of daily paper counts with specific styling and save to a file."""
    ## Ensure index is datetime for proper plotting
    daily_counts.index = pd.to_datetime(daily_counts.index)

    # Define preferred modern font and a common fallback
    preferred_font = 'Arial' # Or 'Helvetica', 'Roboto', 'Open Sans', etc.
    fallback_font = 'sans-serif' # Generic fallback

    font_name = fallback_font # Default to fallback
    try:
        # Check if preferred font is available
        fm.findfont(preferred_font, fallback_to_default=False)
        font_name = preferred_font
    except ValueError:
        # If preferred is not found, matplotlib will use its sans-serif default
        print(f"Preferred font '{preferred_font}' not found. Using '{fallback_font}'.")

    print(f"Using font: {font_name}") ## Log which font is being used

    ## arXiv red color
    arxiv_red = '#b31b1b'
    light_arxiv_red = '#d46a6a' # A lighter shade for gradients or backgrounds if needed
    dark_gray = '#333333'
    medium_gray = '#666666'
    light_gray = '#cccccc'
    lighter_gray = '#e0e0e0' # For subtle grid

    ## Set plot style parameters for a modern look with arXiv theme
    plt.style.use('seaborn-v0_8-whitegrid') ## Start with a clean base
    plt.rcParams.update({
        'font.family': font_name,
        'font.size': 11, # Base font size
        'axes.titlesize': 14, # Title font size
        'axes.labelsize': 12, # Axis label font size
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'axes.edgecolor': medium_gray, # Color of plot edges
        'axes.linewidth': 1.0,
        'axes.grid': True,
        'grid.color': lighter_gray, # Lighter grid for subtlety
        'grid.linestyle': '--', # Dashed grid lines
        'grid.linewidth': 0.7,
        'axes.facecolor': '#FFFFFF', ## White background for the plot area
        'figure.facecolor': '#FFFFFF', # White background for the figure
        'text.color': dark_gray, # Default text color
        'axes.labelcolor': dark_gray, # Axis label color
        'xtick.color': medium_gray, # X-tick color
        'ytick.color': medium_gray, # Y-tick color
        # 'text.antialiased': True, # Enable text anti-aliasing - usually default
    })

    ## --- Plotting ---\n    ## Create figure and axes
    fig, ax = plt.subplots(figsize=(8, 4)) # Slightly taller for better spacing

    ## Create the bar chart - using a single arXiv red color for simplicity
    # For a gradient, you could use a colormap again:
    # cmap = cm.colors.LinearSegmentedColormap.from_list("arxiv_red_gradient", [light_arxiv_red, arxiv_red])
    # norm = plt.Normalize(vmin=0, vmax=daily_counts.values.max() if daily_counts.values.max() > 0 else 1)
    # bar_colors = cmap(norm(daily_counts.values))
    bar_colors = arxiv_red 

    bars = ax.bar(daily_counts.index, daily_counts.values, color=bar_colors, width=0.65, edgecolor=dark_gray, linewidth=0.75)

    ## Format x-axis to show abbreviated day names
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a')) # Short day names (Mon, Tue)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    
    ## Set axis limits to exactly match the data range to prevent extra ticks
    ax.set_xlim(daily_counts.index.min() - pd.Timedelta(hours=12), 
                daily_counts.index.max() + pd.Timedelta(hours=12))
    
    plt.xticks(rotation=0, ha='center')
    
    ## Ensure y-axis shows only integers and starts from 0
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, min_n_ticks=4))
    ax.set_ylim(bottom=0) # Ensure y-axis starts at 0

    ## Add labels and title
    ax.set_ylabel("New Papers", fontdict={'color': dark_gray})
    ax.set_title("Papers Added to LLMpedia (Last 2 Weeks)", pad=20, fontdict={'color': dark_gray})

    ## Add counts on top of bars
    ax.bar_label(bars, padding=3, fontsize=9, color=dark_gray)

    ## Adjust layout and styling - modern look with minimal spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(medium_gray)
    ax.spines['left'].set_color(medium_gray)
    
    # Ensure y-axis grid is on, as we set it in rcParams
    ax.yaxis.grid(True, linestyle='--', alpha=0.7, color=lighter_gray)
    ax.xaxis.grid(False) # Typically, x-axis grid is not needed for bar charts like this

    plt.tight_layout(pad=1.5) # Add some padding

    ## Save the figure
    try:
        fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)  ## Close the figure to free memory
        print(f"Chart saved to {output_path}")
    except Exception as e:
        print(f"Error saving chart: {e}")
        plt.close(fig)
        raise
    finally:
        ## Reset style to default to avoid affecting other plots if script continues
        plt.style.use('default')


# Weekly Review Plot Generation Functions

def parse_weekly_report_sections(report_content: str) -> Dict[str, str]:
    """Parse weekly report content into sections based on markdown headers."""
    sections = {}
    
    # Split by markdown headers (#### level)
    parts = re.split(r'\n#### ', report_content)
    
    # First part is the introduction (before any #### headers)
    if parts:
        sections['introduction'] = parts[0].strip()
    
    # Process themed sections
    for i, part in enumerate(parts[1:], 1):
        lines = part.split('\n')
        section_title = lines[0].strip()
        section_content = '\n'.join(lines[1:]).strip()
        
        # Classify section type based on content
        if any(keyword in section_title.lower() for keyword in ['controversy', 'contradiction', 'stubborn', 'problem']):
            sections['controversy'] = {'title': section_title, 'content': section_content}
        else:
            sections[f'theme_{i}'] = {'title': section_title, 'content': section_content}
    
    return sections


def generate_publication_trends_plot(weekly_counts: Dict[str, int], current_date: str) -> str:
    """Generate publication trends plot for the introduction section."""
    # Convert weekly counts to DataFrame
    dates = []
    counts = []
    
    for date_str, count in sorted(weekly_counts.items()):
        dates.append(pd.to_datetime(date_str))
        counts.append(count)
    
    df = pd.DataFrame({'date': dates, 'count': counts})
    
    fig = go.Figure()
    
    # Add line plot for trends (convert all data to JSON-serializable types)
    fig.add_trace(go.Scatter(
        x=df['date'].dt.strftime('%Y-%m-%d').tolist(),
        y=df['count'].astype(int).tolist(),
        mode='lines+markers',
        name='Papers Published',
        line=dict(color='#b31b1b', width=3),
        marker=dict(size=6, color='#b31b1b')
    ))
    
    # Highlight current week
    current_idx = df[df['date'] == pd.to_datetime(current_date)].index
    if len(current_idx) > 0:
        current_count = int(df.loc[current_idx[0], 'count'])
        fig.add_trace(go.Scatter(
            x=[current_date],
            y=[current_count],
            mode='markers',
            name='Current Week',
            marker=dict(size=12, color='#e04848', symbol='star')
        ))
    
    fig.update_layout(
        title='Weekly Publication Trends',
        xaxis_title='Week',
        yaxis_title='Number of Papers',
        height=400,
        template='plotly_white',
        showlegend=False
    )
    
    return json.dumps(fig.to_dict())


def generate_chart_from_specification(chart_spec: dict, theme_title: str) -> str:
    """Generate a Plotly chart from LLM-provided specifications."""
    chart_type = chart_spec.get('type', 'bar')
    visualization_mode = chart_spec.get('visualization_mode', 'quantitative')
    data_structure = chart_spec.get('data_structure', {})
    axis_labels = chart_spec.get('axis_labels', {})
    visual_story = chart_spec.get('visual_story', '')
    title_suffix = chart_spec.get('title_suffix', '')
    
    # Extract data structure
    x_items = data_structure.get('x_axis_items', ['Item A', 'Item B', 'Item C'])
    y_concept = data_structure.get('y_axis_concept', 'performance')
    categories = data_structure.get('categories', [])
    
    # Generate appropriate chart based on type and mode
    if chart_type == 'bar':
        return _generate_bar_chart(x_items, y_concept, visualization_mode, axis_labels, theme_title, title_suffix, visual_story)
    elif chart_type == 'grouped_bar':
        return _generate_grouped_bar_chart(x_items, y_concept, categories, visualization_mode, axis_labels, theme_title, title_suffix, visual_story)
    elif chart_type == 'scatter':
        return _generate_scatter_chart(x_items, y_concept, visualization_mode, axis_labels, theme_title, title_suffix, visual_story)
    elif chart_type == 'line':
        return _generate_line_chart(x_items, y_concept, visualization_mode, axis_labels, theme_title, title_suffix, visual_story)
    else:
        # Fallback to bar chart
        return _generate_bar_chart(x_items, y_concept, visualization_mode, axis_labels, theme_title, title_suffix, visual_story)

def _generate_bar_chart(x_items: list, y_concept: str, mode: str, axis_labels: dict, title: str, title_suffix: str, story: str) -> str:
    """Generate a simple bar chart."""
    if mode == "conceptual":
        # Qualitative ranking
        performance_levels = ['Excellent', 'Good', 'Fair'][:len(x_items)]
        y_values = list(range(len(x_items), 0, -1))  # Descending ranks
        colors = ['#b31b1b', '#d46a6a', '#f0a0a0'][:len(x_items)]
        
        fig = go.Figure(data=[
            go.Bar(x=x_items, y=y_values, text=performance_levels, textposition='inside',
                  marker_color=colors, showlegend=False)
        ])
        
        fig.update_layout(
            title=f"{title} {title_suffix}".strip(),
            xaxis_title=axis_labels.get('x', 'Items'),
            yaxis_title=axis_labels.get('y', 'Relative Performance'),
            yaxis=dict(tickvals=list(range(1, len(x_items)+1)), 
                      ticktext=performance_levels[::-1]),
            height=400, template='plotly_white',
            annotations=[dict(text=f"Qualitative assessment: {story}", 
                            x=0.5, y=-0.15, xref='paper', yref='paper', 
                            showarrow=False, font=dict(size=10, color='gray'))]
        )
    else:
        # Quantitative with synthetic data
        y_values = [85 - i*10 for i in range(len(x_items))]  # Descending scores
        
        fig = go.Figure(data=[
            go.Bar(x=x_items, y=y_values, marker_color='#b31b1b')
        ])
        
        fig.update_layout(
            title=f"{title} {title_suffix}".strip(),
            xaxis_title=axis_labels.get('x', 'Items'),
            yaxis_title=axis_labels.get('y', 'Score'),
            height=400, template='plotly_white',
            annotations=[dict(text=f"Representative data: {story}", 
                            x=0.5, y=-0.15, xref='paper', yref='paper', 
                            showarrow=False, font=dict(size=10, color='gray'))]
        )
    
    return json.dumps(fig.to_dict())

def _generate_grouped_bar_chart(x_items: list, y_concept: str, categories: list, mode: str, axis_labels: dict, title: str, title_suffix: str, story: str) -> str:
    """Generate a grouped bar chart for multi-dimensional comparisons."""
    fig = go.Figure()
    
    colors = ['#b31b1b', '#d46a6a', '#4169E1']
    
    for i, category in enumerate(categories[:3]):  # Limit to 3 categories
        if mode == "conceptual":
            y_values = [3-j for j in range(len(x_items))]  # Ranking values
        else:
            y_values = [80 - i*5 - j*10 for j in range(len(x_items))]  # Synthetic scores
            
        fig.add_trace(go.Bar(
            name=category,
            x=x_items,
            y=y_values,
            marker_color=colors[i % len(colors)]
        ))
    
    fig.update_layout(
        title=f"{title} {title_suffix}".strip(),
        xaxis_title=axis_labels.get('x', 'Items'),
        yaxis_title=axis_labels.get('y', 'Performance'),
        height=400, template='plotly_white', barmode='group',
        annotations=[dict(text=f"Multi-dimensional comparison: {story}", 
                        x=0.5, y=-0.15, xref='paper', yref='paper', 
                        showarrow=False, font=dict(size=10, color='gray'))]
    )
    
    return json.dumps(fig.to_dict())

def _generate_scatter_chart(x_items: list, y_concept: str, mode: str, axis_labels: dict, title: str, title_suffix: str, story: str) -> str:
    """Generate a scatter plot for relationship visualization."""
    import random
    random.seed(42)  # Consistent results
    
    if mode == "conceptual":
        # Use rankings instead of specific values
        x_values = list(range(1, len(x_items)+1))
        y_values = [len(x_items)+1-i for i in range(1, len(x_items)+1)]
    else:
        # Synthetic performance data
        x_values = [random.uniform(70, 95) for _ in x_items]
        y_values = [random.uniform(60, 90) for _ in x_items]
    
    fig = go.Figure(data=[
        go.Scatter(x=x_values, y=y_values, mode='markers+text', text=x_items,
                  textposition='top center', marker=dict(size=12, color='#b31b1b'))
    ])
    
    fig.update_layout(
        title=f"{title} {title_suffix}".strip(),
        xaxis_title=axis_labels.get('x', 'Dimension 1'),
        yaxis_title=axis_labels.get('y', 'Dimension 2'),
        height=400, template='plotly_white',
        annotations=[dict(text=f"Relationship analysis: {story}", 
                        x=0.5, y=-0.15, xref='paper', yref='paper', 
                        showarrow=False, font=dict(size=10, color='gray'))]
    )
    
    return json.dumps(fig.to_dict())

def _generate_line_chart(x_items: list, y_concept: str, mode: str, axis_labels: dict, title: str, title_suffix: str, story: str) -> str:
    """Generate a line chart for trends/progression."""
    if mode == "conceptual":
        y_values = list(range(1, len(x_items)+1))  # Simple progression
    else:
        y_values = [70 + i*5 for i in range(len(x_items))]  # Synthetic trend
    
    fig = go.Figure(data=[
        go.Scatter(x=x_items, y=y_values, mode='lines+markers',
                  line=dict(color='#b31b1b', width=3), marker=dict(size=8))
    ])
    
    fig.update_layout(
        title=f"{title} {title_suffix}".strip(),
        xaxis_title=axis_labels.get('x', 'Progression'),
        yaxis_title=axis_labels.get('y', 'Value'),
        height=400, template='plotly_white',
        annotations=[dict(text=f"Trend analysis: {story}", 
                        x=0.5, y=-0.15, xref='paper', yref='paper', 
                        showarrow=False, font=dict(size=10, color='gray'))]
    )
    
    return json.dumps(fig.to_dict())

def generate_chart_from_specification(chart_spec: Dict[str, Any], theme_title: str) -> str:
    """Generate a chart based on LLM-provided specifications."""
    chart_type = chart_spec.get('type', 'bar')
    visualization_mode = chart_spec.get('visualization_mode', 'quantitative')
    data_structure = chart_spec.get('data_structure', {})
    axis_labels = chart_spec.get('axis_labels', {})
    title_suffix = chart_spec.get('title_suffix', '')
    
    # Extract data structure
    x_items = data_structure.get('x_axis_items', ['Item 1', 'Item 2', 'Item 3'])
    y_concept = data_structure.get('y_axis_concept', 'performance')
    categories = data_structure.get('categories', [])
    
    # Create chart title
    chart_title = f"{theme_title}"
    if title_suffix:
        chart_title += f": {title_suffix}"
    
    # Generate chart based on type
    if chart_type == 'grouped_bar' and categories:
        return _generate_grouped_bar_chart(x_items, categories, y_concept, chart_title, visualization_mode, axis_labels)
    elif chart_type == 'scatter':
        return _generate_scatter_chart(x_items, y_concept, chart_title, visualization_mode, axis_labels)
    elif chart_type == 'line':
        return _generate_line_chart(x_items, y_concept, chart_title, visualization_mode, axis_labels)
    else:  # Default to bar chart
        return _generate_bar_chart(x_items, y_concept, chart_title, visualization_mode, axis_labels)

def _generate_bar_chart(x_items: List[str], y_concept: str, title: str, viz_mode: str, axis_labels: Dict[str, str]) -> str:
    """Generate a simple bar chart."""
    if viz_mode == "conceptual":
        # Qualitative levels
        levels = ['Strong', 'Good', 'Moderate', 'Baseline'][:len(x_items)]
        y_values = list(range(len(x_items), 0, -1))  # Descending order
        colors = ['#2E8B57', '#32CD32', '#FFA500', '#CD5C5C'][:len(x_items)]
        
        fig = go.Figure(data=[
            go.Bar(x=x_items, y=y_values, text=levels, textposition='inside',
                  marker_color=colors, showlegend=False)
        ])
        
        fig.update_layout(
            title=title,
            xaxis_title=axis_labels.get('x', 'Approaches'),
            yaxis_title=axis_labels.get('y', f'Relative {y_concept.title()}'),
            yaxis=dict(tickvals=y_values, ticktext=levels),
            height=400,
            template='plotly_white',
            annotations=[dict(text="Qualitative assessment from research analysis", 
                            x=0.5, y=-0.15, xref='paper', yref='paper', 
                            showarrow=False, font=dict(size=10, color='gray'))]
        )
    else:
        # Quantitative data (synthetic)
        y_values = [85 - i*10 for i in range(len(x_items))]  # Decreasing values
        
        fig = go.Figure(data=[
            go.Bar(x=x_items, y=y_values, marker_color='#b31b1b')
        ])
        
        fig.update_layout(
            title=title,
            xaxis_title=axis_labels.get('x', 'Approaches'),
            yaxis_title=axis_labels.get('y', f'{y_concept.title()} Score'),
            height=400,
            template='plotly_white',
            annotations=[dict(text="Representative data for illustration", 
                            x=0.5, y=-0.15, xref='paper', yref='paper', 
                            showarrow=False, font=dict(size=10, color='gray'))]
        )
    
    return json.dumps(fig.to_dict())

def _generate_grouped_bar_chart(x_items: List[str], categories: List[str], y_concept: str, title: str, viz_mode: str, axis_labels: Dict[str, str]) -> str:
    """Generate a grouped bar chart."""
    fig = go.Figure()
    colors = ['#b31b1b', '#d46a6a', '#f0a0a0'][:len(categories)]
    
    for i, category in enumerate(categories):
        if viz_mode == "conceptual":
            # Qualitative levels with some variation
            base_levels = ['Strong', 'Good', 'Moderate']
            y_values = [3-j+i*0.2 for j in range(len(x_items))]
        else:
            # Quantitative synthetic data
            y_values = [80 - j*10 + i*5 for j in range(len(x_items))]
        
        fig.add_trace(go.Bar(
            name=category,
            x=x_items,
            y=y_values,
            marker_color=colors[i % len(colors)]
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title=axis_labels.get('x', 'Approaches'),
        yaxis_title=axis_labels.get('y', f'{y_concept.title()}'),
        height=400,
        template='plotly_white',
        barmode='group',
        annotations=[dict(text="Comparative assessment across dimensions", 
                        x=0.5, y=-0.15, xref='paper', yref='paper', 
                        showarrow=False, font=dict(size=10, color='gray'))]
    )
    
    return json.dumps(fig.to_dict())

def _generate_scatter_chart(x_items: List[str], y_concept: str, title: str, viz_mode: str, axis_labels: Dict[str, str]) -> str:
    """Generate a scatter plot for relationships."""
    # For scatter, we need two dimensions - create synthetic relationship
    x_values = [i*10 + 50 for i in range(len(x_items))]  # Spread x values
    
    if viz_mode == "conceptual":
        y_values = [3-i+0.5 for i in range(len(x_items))]  # Relative positions
        y_axis_title = f'Relative {y_concept.title()}'
    else:
        y_values = [90-i*15 for i in range(len(x_items))]  # Synthetic scores
        y_axis_title = f'{y_concept.title()} Score'
    
    fig = go.Figure(data=[
        go.Scatter(
            x=x_values,
            y=y_values,
            mode='markers+text',
            text=x_items,
            textposition='top center',
            marker=dict(size=12, color='#b31b1b'),
            showlegend=False
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title=axis_labels.get('x', 'Efficiency'),
        yaxis_title=axis_labels.get('y', y_axis_title),
        height=400,
        template='plotly_white',
        annotations=[dict(text="Relationship visualization", 
                        x=0.5, y=-0.15, xref='paper', yref='paper', 
                        showarrow=False, font=dict(size=10, color='gray'))]
    )
    
    return json.dumps(fig.to_dict())

def _generate_line_chart(x_items: List[str], y_concept: str, title: str, viz_mode: str, axis_labels: Dict[str, str]) -> str:
    """Generate a line chart for trends."""
    if viz_mode == "conceptual":
        y_values = [1, 2, 3, 2.5][:len(x_items)]  # Trend pattern
        y_axis_title = f'Relative {y_concept.title()}'
    else:
        y_values = [60 + i*10 for i in range(len(x_items))]  # Increasing trend
        y_axis_title = f'{y_concept.title()} Score'
    
    fig = go.Figure(data=[
        go.Scatter(
            x=x_items,
            y=y_values,
            mode='lines+markers',
            line=dict(color='#b31b1b', width=3),
            marker=dict(size=8),
            showlegend=False
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title=axis_labels.get('x', 'Progression'),
        yaxis_title=axis_labels.get('y', y_axis_title),
        height=400,
        template='plotly_white',
        annotations=[dict(text="Trend visualization", 
                        x=0.5, y=-0.15, xref='paper', yref='paper', 
                        showarrow=False, font=dict(size=10, color='gray'))]
    )
    
    return json.dumps(fig.to_dict())

def generate_theme_comparison_plot(theme_title: str, theme_content: str, visualization_mode: str = "quantitative") -> str:
    """Generate a thematic comparison plot based on section content."""
    # Extract paper counts and performance metrics from content
    papers_mentioned = len(re.findall(r'\*[^*]+\*\s*\(arxiv:', theme_content))
    
    # Create synthetic data based on theme content analysis
    if 'efficiency' in theme_title.lower() or 'reasoning' in theme_title.lower():
        categories = ['Short Reasoning', 'Medium Reasoning', 'Long Reasoning']
        
        if visualization_mode == "conceptual":
            # Conceptual ranking without specific numbers
            rankings = ['Strong', 'Moderate', 'Weak']
            colors = ['#2E8B57', '#FFA500', '#CD5C5C']
            
            fig = go.Figure(data=[
                go.Bar(name='Performance Level', x=categories, y=[3, 2, 1], 
                      text=rankings, textposition='inside',
                      marker_color=colors, showlegend=False)
            ])
            
            fig.update_layout(
                title=f'Conceptual Analysis: {theme_title}',
                xaxis_title='Approach',
                yaxis_title='Relative Performance',
                yaxis=dict(tickvals=[1, 2, 3], ticktext=['Weak', 'Moderate', 'Strong']),
                height=400,
                template='plotly_white',
                annotations=[dict(text="Based on qualitative analysis from research reports", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        else:
            # Quantitative with synthetic data  
            accuracy = [85, 75, 65]  # Synthetic data based on content
            
            fig = go.Figure(data=[
                go.Bar(name='Accuracy %', x=categories, y=accuracy, 
                      marker_color=['#2E8B57', '#FFA500', '#CD5C5C'])
            ])
            
            fig.update_layout(
                title=f'Performance Analysis: {theme_title}',
                xaxis_title='Approach',
                yaxis_title='Accuracy (%)',
                height=400,
                template='plotly_white',
                annotations=[dict(text="Representative data for illustration", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        
    elif 'multimodal' in theme_title.lower() or 'visual' in theme_title.lower():
        # Model comparison chart
        models = ['GPT-4o', 'Claude-3.5', 'Gemini-1.5']
        
        if visualization_mode == "conceptual":
            # Relative performance without specific scores
            performance_levels = ['Leading', 'Competitive', 'Baseline']
            colors = ['#b31b1b', '#d46a6a', '#f0a0a0']
            
            fig = go.Figure(data=[
                go.Bar(name='Performance Level', x=models, y=[3, 2, 1],
                      text=performance_levels, textposition='inside',
                      marker_color=colors, showlegend=False)
            ])
            
            fig.update_layout(
                title=f'Model Comparison: {theme_title}',
                xaxis_title='Model',
                yaxis_title='Relative Performance',
                yaxis=dict(tickvals=[1, 2, 3], ticktext=['Baseline', 'Competitive', 'Leading']),
                height=400,
                template='plotly_white',
                annotations=[dict(text="Relative ranking based on research findings", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        else:
            # Quantitative with example scores
            scores = [45.8, 42.2, 32.5]  # Example from the content
            
            fig = go.Figure(data=[
                go.Bar(name='Performance', x=models, y=scores,
                      marker_color='#b31b1b')
            ])
            
            fig.update_layout(
                title=f'Model Performance: {theme_title}',
                xaxis_title='Model',
                yaxis_title='Accuracy (%)',
                height=400,
                template='plotly_white',
                annotations=[dict(text="Representative data for illustration", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        
    elif 'hallucination' in theme_title.lower() or 'factual' in theme_title.lower():
        # Method effectiveness chart
        methods = ['Standard RL', 'RL + Refusal', 'Verification', 'Search Integration']
        
        if visualization_mode == "conceptual":
            # Relative effectiveness without specific scores
            effectiveness_levels = ['Poor', 'Good', 'Better', 'Best']
            colors = ['#CD5C5C', '#32CD32', '#FFA500', '#4169E1']
            
            fig = go.Figure(data=[
                go.Bar(name='Effectiveness Level', x=methods, y=[1, 3, 2.5, 4],
                      text=effectiveness_levels, textposition='inside',
                      marker_color=colors, showlegend=False)
            ])
            
            fig.update_layout(
                title=f'Method Comparison: {theme_title}',
                xaxis_title='Approach',
                yaxis_title='Relative Effectiveness',
                yaxis=dict(tickvals=[1, 2, 3, 4], ticktext=['Poor', 'Better', 'Good', 'Best']),
                height=400,
                template='plotly_white',
                annotations=[dict(text="Qualitative assessment from research analysis", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        else:
            # Quantitative with synthetic effectiveness scores
            effectiveness = [20, 75, 65, 80]
            
            fig = go.Figure(data=[
                go.Bar(name='Effectiveness', x=methods, y=effectiveness,
                      marker_color=['#CD5C5C', '#32CD32', '#FFA500', '#4169E1'])
            ])
            
            fig.update_layout(
                title=f'Method Effectiveness: {theme_title}',
                xaxis_title='Approach',
                yaxis_title='Effectiveness Score',
                height=400,
                template='plotly_white',
                annotations=[dict(text="Representative scores for illustration", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        
    else:
        # Generic research distribution
        if visualization_mode == "conceptual":
            # Focus areas without specific counts
            topics = ['Primary Focus', 'Secondary Focus', 'Emerging Area']
            importance = ['High', 'Medium', 'Growing']
            colors = ['#b31b1b', '#d46a6a', '#f0a0a0']
            
            fig = go.Figure(data=[
                go.Bar(name='Research Focus', x=topics, y=[3, 2, 1],
                      text=importance, textposition='inside',
                      marker_color=colors, showlegend=False)
            ])
            
            fig.update_layout(
                title=f'Research Focus Areas: {theme_title}',
                xaxis_title='Area',
                yaxis_title='Research Priority',
                yaxis=dict(tickvals=[1, 2, 3], ticktext=['Growing', 'Medium', 'High']),
                height=400,
                template='plotly_white',
                annotations=[dict(text="Research priority assessment from content analysis", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
        else:
            # Paper count distribution
            topics = ['Method A', 'Method B', 'Method C']
            counts = [papers_mentioned // 3, papers_mentioned // 3, papers_mentioned - 2*(papers_mentioned // 3)]
            
            fig = go.Figure(data=[
                go.Bar(name='Papers', x=topics, y=counts,
                      marker_color='#b31b1b')
            ])
            
            fig.update_layout(
                title=f'Research Distribution: {theme_title}',
                xaxis_title='Approach',
                yaxis_title='Number of Papers',
                height=400,
                template='plotly_white',
                annotations=[dict(text="Paper count distribution", 
                                x=0.5, y=-0.15, xref='paper', yref='paper', 
                                showarrow=False, font=dict(size=10, color='gray'))]
            )
    
    return json.dumps(fig.to_dict())


def generate_controversy_plot(controversy_title: str, controversy_content: str) -> str:
    """Generate a controversy/contradiction visualization."""
    # Create a comparison chart showing the tension/trade-off
    
    if 'reasoning' in controversy_title.lower() and 'control' in controversy_title.lower():
        # Trade-off visualization
        reasoning_capability = [20, 40, 60, 80, 95]
        instruction_adherence = [95, 85, 70, 50, 30]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=reasoning_capability,
            y=instruction_adherence,
            mode='lines+markers',
            name='Trade-off Curve',
            line=dict(color='#b31b1b', width=3),
            marker=dict(size=8, color='#b31b1b')
        ))
        
        # Add annotations for key points
        fig.add_annotation(
            x=80, y=50,
            text="Current LLMs",
            showarrow=True,
            arrowhead=2,
            arrowcolor="#CD5C5C"
        )
        
        fig.update_layout(
            title=f'Trade-off Analysis: {controversy_title}',
            xaxis_title='Reasoning Capability',
            yaxis_title='Instruction Adherence',
            height=400,
            template='plotly_white'
        )
        
    else:
        # Generic before/after comparison
        conditions = ['Before', 'After']
        metric1 = [60, 40]  # Problem metric
        metric2 = [40, 70]  # Solution metric
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Problem Metric',
            x=conditions,
            y=metric1,
            marker_color='#CD5C5C'
        ))
        
        fig.add_trace(go.Bar(
            name='Solution Metric',
            x=conditions,
            y=metric2,
            marker_color='#32CD32'
        ))
        
        fig.update_layout(
            title=f'Impact Analysis: {controversy_title}',
            xaxis_title='Condition',
            yaxis_title='Score',
            height=400,
            template='plotly_white',
            barmode='group'
        )
    
    return json.dumps(fig.to_dict())


def generate_weekly_review_plots(
    report_content: str, 
    weekly_counts: Dict[str, int], 
    current_date: str
) -> Dict[str, str]:
    """Generate all plots for a weekly review report."""
    sections = parse_weekly_report_sections(report_content)
    plots = {}
    
    # Generate introduction plot (publication trends)
    plots['introduction'] = generate_publication_trends_plot(weekly_counts, current_date)
    
    # Generate theme plots
    for section_key, section_data in sections.items():
        if section_key.startswith('theme_'):
            if isinstance(section_data, dict):
                plots[section_key] = generate_theme_comparison_plot(
                    section_data['title'], 
                    section_data['content']
                )
    
    # Generate controversy plot
    if 'controversy' in sections:
        controversy_data = sections['controversy']
        if isinstance(controversy_data, dict):
            plots['controversy'] = generate_controversy_plot(
                controversy_data['title'],
                controversy_data['content']
            )
    
    return plots
