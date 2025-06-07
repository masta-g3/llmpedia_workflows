import json
from pathlib import Path
import os

## --- Component Loading (Copied from utils/data_cards.py for standalone use) --- 
## Path to component definitions relative to this file's location
COMPONENT_DIR = Path(__file__).parent.parent / "utils" / "data_cards" / "components"

def load_component_definitions_for_prompt():
    """Load component definitions for embedding into the LLM prompt."""
    definitions = []
    if not COMPONENT_DIR.is_dir():
        print(f"Warning: Component directory not found for prompt generation: {COMPONENT_DIR}")
        return definitions
        
    for filename in sorted(os.listdir(COMPONENT_DIR)):
        if filename.endswith(".json"):
            filepath = COMPONENT_DIR / filename
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    component_id = data.get("component_id")
                    if component_id:
                        definitions.append({
                            "id": component_id,
                            "name": data.get("name", component_id),
                            "description": data.get("description", "No description provided."),
                        })
                    else:
                         print(f"Warning: Component ID missing in {filename}")
            except Exception as e:
                print(f"Error loading component definition {filename} for prompt: {e}")
    return definitions

## Load definitions when the module is imported
AVAILABLE_COMPONENTS = load_component_definitions_for_prompt()

## Dynamically build the component list string for the prompt
component_list_string = "\n".join(
    f"- **`{comp['id']}`**: {comp['name']} - {comp['description']}" 
    for comp in AVAILABLE_COMPONENTS
)

## --- Main Prompt Definition --- 

# Note: This prompt structure uses placeholders like {title} and {content}
# which are expected to be filled by the calling Python code.
DATA_CARD_COMPONENT_PROMPT = f"""
You are an expert AI assistant specialized in analyzing scientific whitepapers and creating engaging, informative data card dashboards using a predefined component system.

Your task is to read the provided whitepaper and generate two pieces of output:
1. A concise 2-3 sentence summary of the paper's main contributions and findings.
2. A JSON structure describing a 5-tab dashboard, where each tab uses one of the available components to visualize or present a key aspect of the paper.

**Input Whitepaper:**
<whitepaper>
Title: {{title}}

Content:
{{content}}
</whitepaper>

**Instructions:**

1.  **Analyze Thoroughly:** Read the paper carefully to identify the most important findings, methods, results, and conclusions.
2.  **Summarize:** Write a concise 2-3 sentence summary encapsulating the paper's core message. Place this inside `<summary>` tags.
3.  **Design the Dashboard:** Plan a 5-tab dashboard (4 for findings/key points, 1 for conclusion/implications). For each tab:
    *   Identify a specific, interesting point or finding from the paper.
    *   Choose the **most appropriate component** from the list below to present that information.
    *   Aim for **diversity** in the components used across the tabs. Do not use the same chart type (e.g., BarChart) more than once if possible.
    *   Extract the necessary data or text from the paper to populate the chosen component.
    *   If specific numerical data is sparse, you may invent plausible data points *clearly derived from the paper's context* to illustrate a finding (e.g., showing a trend mentioned qualitatively).
    *   Write a clear, engaging title for the tab.
    *   Write a descriptive paragraph explaining the finding in simple terms.
    *   Optionally, add a brief 'note' for clarification or interpretation.
4.  **Format Output:** Structure your output exactly as follows:
    *   Start with the summary inside `<summary>...</summary>` tags.
    *   Follow with the dashboard structure inside `<dashboard_structure>...</dashboard_structure>` tags.
    *   The content inside `<dashboard_structure>` must be a valid JSON array `[...]`.
    *   Each object in the array represents one tab and must have these keys:
        *   `"tab_id"`: A unique string identifier for the tab (e.g., `"finding1"`, `"method_comparison"`, `"conclusion"`).
        *   `"title"`: A string for the tab's title (e.g., `"Vocabulary Extension Impact"`).
        *   `"description"`: A string containing the paragraph explaining the finding.
        *   `"note"`: An optional string for the brief note below the component.
        *   `"chosen_component_id"`: A string matching the ID of the selected component from the list below (e.g., `"bar_chart_v1"`).
        *   `"filled_parameters"`: A JSON object containing the data needed by the chosen component. **The structure of this object MUST match the expected input for the chosen component.** See examples below.

**Available Components:**

{component_list_string}

**Parameter Structure Examples (`filled_parameters`):**

*   **For `bar_chart_v1`:** Expects `{{ "data": [{{ "category": "string", "value1": number, "value1_name": "string", "value2": number?, "value2_name": "string"? }}], "x_axis_label": string?, "y_axis_label": string? }}`
*   **For `line_chart_v1`:** Expects `{{ "data": [{{ "x_value": string|number, "y_value1": number, "y_value1_name": "string", "y_value2": number?, "y_value2_name": "string"? }}], "x_axis_label": string?, "y_axis_label": string? }}`
*   **For `pie_chart_v1`:** Expects `{{ "data": [{{ "name": "string", "value": number }}] }}`
*   **For `list_v1`:** Expects `{{ "items": ["string", ...], "ordered": boolean? }}`
*   **For `key_value_v1`:** Expects `{{ "items": [{{ "key": "string", "value": "string" }}] }}`
*   **For `quote_v1`:** Expects `{{ "text": "string", "source": string? }}`
*   **For `image_v1`:** Expects `{{ "image_url": "string (URL)", "alt_text": "string", "caption": string? }}`
*   **(Refer to component descriptions for others)**

**General Guidelines:**

*   **Accuracy:** Ensure all extracted information and conclusions accurately reflect the paper's content.
*   **Clarity:** Use simple, accessible language. Avoid jargon or explain technical terms clearly.
*   **Conciseness:** Keep titles, descriptions, and notes focused.
*   **Data:** Prioritize using actual data from the paper. Invent data sparingly only when necessary to illustrate a point clearly described in the text, and ensure it's plausible.
*   **Visual Appeal:** While you don't control the final styling, structure the information logically for a clear presentation.
*   **Focus:** Select the most impactful or interesting findings to highlight.
*   **Unexpected Findings:** Try to include at least one surprising or counter-intuitive result if present in the paper.

Produce **only** the `<summary>` and `<dashboard_structure>` sections.
"""

## Example Usage (for testing the prompt string itself)
if __name__ == '__main__':
    # Create a dummy title and content
    test_title = "Example Paper Title"
    test_content = "This is the content of the example paper. It discusses method A and method B. Method A achieves 90% accuracy, while method B achieves 95%. It also presents results over time. We conclude that method B is superior."
    
    # Format the prompt
    formatted_prompt = DATA_CARD_COMPONENT_PROMPT.format(title=test_title, content=test_content)
    
    # Print a snippet
    print(formatted_prompt[:2000]) # Print the first part of the prompt
    print("\n...")
    print(f"Total prompt length: {len(formatted_prompt)} characters")
    print(f"Number of available components: {len(AVAILABLE_COMPONENTS)}") 