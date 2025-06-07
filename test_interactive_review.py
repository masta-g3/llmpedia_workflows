#!/usr/bin/env python3
"""
Test script for the interactive weekly review functionality.
This script tests the components without requiring database access.
"""

import json
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add project path
PROJECT_PATH = os.getenv("PROJECT_PATH", "/Users/manager/Code/llmpedia_workflows")
sys.path.append(PROJECT_PATH)

import utils.interactive_components as ic

def create_mock_structured_content():
    """Create mock structured content for testing."""
    return {
        "intro": {
            "content": "This week saw 25 papers published in machine learning, focusing on three main themes: multimodal learning, efficiency improvements, and ethical AI development.",
            "trends_data": {
                "volume_observation": "Publication volume increased 15% compared to last week",
                "main_themes": ["Multimodal Learning", "Model Efficiency", "AI Ethics"]
            }
        },
        "themes": [
            {
                "title": "Multimodal Learning Breakthroughs",
                "content": "Three significant papers introduced novel architectures for vision-language tasks, with improvements in cross-modal attention mechanisms.",
                "papers": ["2401.12345", "2401.67890"],
                "concepts": ["cross-modal attention", "vision-language fusion", "multimodal architectures"],
                "chart_specification": {
                    "type": "bar",
                    "visualization_mode": "conceptual",
                    "data_structure": {
                        "x_axis_items": ["GPT-4o", "Claude-3.5", "Gemini-1.5"],
                        "y_axis_concept": "multimodal_performance",
                        "categories": []
                    },
                    "visual_story": "Comparison of leading models on multimodal tasks",
                    "axis_labels": {
                        "x": "Model",
                        "y": "Multimodal Capability"
                    },
                    "title_suffix": "Performance"
                }
            },
            {
                "title": "Efficiency and Optimization",
                "content": "Several papers focused on reducing computational costs while maintaining model performance through novel pruning and quantization techniques.",
                "papers": ["2401.11111", "2401.22222"],
                "concepts": ["model pruning", "quantization", "efficient training"],
                "metrics_suggested": {
                    "visualization_type": "scatter",
                    "visualization_mode": "quantitative",
                    "key_metrics": ["speedup", "accuracy_retention"],
                    "comparison_axis": "performance"
                }
            }
        ],
        "controversy": {
            "title": "Scaling Laws vs Emergent Capabilities",
            "content": "The community remains divided on whether model capabilities emerge predictably through scaling laws or represent genuine phase transitions.",
            "opposing_papers": [
                {
                    "side": "Predictable Scaling",
                    "papers": ["2401.33333"],
                    "position": "Capabilities follow smooth scaling laws"
                },
                {
                    "side": "Emergent Properties",
                    "papers": ["2401.44444"],
                    "position": "Capabilities emerge unpredictably"
                }
            ]
        }
    }

def create_mock_interactive_components():
    """Create mock interactive components for testing."""
    return {
        "trends": {
            "type": "line_chart",
            "data": [
                {"x_value": "Jan 15", "y_value1": 18, "y_value1_name": "Papers Published"},
                {"x_value": "Jan 22", "y_value1": 22, "y_value1_name": "Papers Published"},
                {"x_value": "Jan 29", "y_value1": 25, "y_value1_name": "Papers Published"}
            ],
            "config": {"title": "Weekly Publication Trends"},
            "insights": "Steady increase in publication volume"
        },
        "themes": [
            {
                "theme_data": {
                    "title": "Multimodal Learning Breakthroughs",
                    "content": "Three significant papers introduced novel architectures.",
                    "papers": ["2401.12345", "2401.67890"],
                    "concepts": ["cross-modal attention"],
                    "chart_specification": {
                        "type": "grouped_bar",
                        "visualization_mode": "conceptual",
                        "data_structure": {
                            "x_axis_items": ["GPT-4o", "Claude-3.5", "Gemini-1.5"],
                            "y_axis_concept": "capability",
                            "categories": ["Vision", "Language", "Reasoning"]
                        },
                        "visual_story": "Compare multimodal capabilities across different dimensions",
                        "axis_labels": {
                            "x": "AI Models",
                            "y": "Capability Level"
                        },
                        "title_suffix": "Capability Analysis"
                    }
                },
                "visualization": {
                    "type": "bar",
                    "data": [
                        {"label": "Paper A", "value": 89, "category": "Vision-Language"},
                        {"label": "Paper B", "value": 92, "category": "Architecture"}
                    ],
                    "insights": "Strong performance across all papers"
                }
            }
        ],
        "controversy": {
            "type": "divergent_bar",
            "data": [
                {"side": "Predictable Scaling", "papers_count": 3, "strength": 65},
                {"side": "Emergent Properties", "papers_count": 4, "strength": 75}
            ],
            "insights": "Community slightly favors emergent properties view"
        }
    }

def create_mock_weekly_counts():
    """Create mock weekly publication counts."""
    base_date = datetime.now() - timedelta(weeks=16)
    weekly_counts = {}
    
    for i in range(16):
        week_date = base_date + timedelta(weeks=i)
        monday = week_date - timedelta(days=week_date.weekday())
        date_str = monday.strftime("%Y-%m-%d")
        # Mock data with some variation
        count = 18 + (i % 3) * 3 + (i // 4) * 2
        weekly_counts[date_str] = count
    
    return weekly_counts

def test_simple_chart_generation():
    """Test the simple chart generation functions."""
    print("Testing simple chart generation...")
    
    # Test theme chart
    theme_params = {
        "theme_title": "Test Theme",
        "theme_content": "This is a test theme content.",
        "visualization_data": [
            {"label": "Test Item 1", "value": 85},
            {"label": "Test Item 2", "value": 92}
        ],
        "papers": [
            {"arxiv_code": "2401.12345", "title": "Test Paper 1"}
        ],
        "insights": "Test insights"
    }
    
    theme_html = ic.generate_simple_chart_html(theme_params, "theme")
    assert "Test Theme" in theme_html
    assert "Test Item 1" in theme_html
    print("✓ Theme chart generation works")
    
    # Test trends chart
    trends_params = {
        "data": [
            {"x_value": "Week 1", "y_value1": 20},
            {"x_value": "Week 2", "y_value1": 25}
        ]
    }
    
    trends_html = ic.generate_simple_chart_html(trends_params, "trends")
    assert "Weekly Publication Trends" in trends_html
    assert "Week 1" in trends_html
    print("✓ Trends chart generation works")

def test_interactive_report_assembly():
    """Test the interactive report assembly."""
    print("Testing interactive report assembly...")
    
    structured_content = create_mock_structured_content()
    interactive_components = create_mock_interactive_components()
    weekly_counts = create_mock_weekly_counts()
    
    try:
        html_content = ic.assemble_interactive_report_html(
            structured_content,
            interactive_components,
            weekly_counts
        )
        
        # Check that key elements are present
        assert "Interactive Weekly Review" in html_content
        assert "Multimodal Learning Breakthroughs" in html_content
        assert "Publication Trends" in html_content
        print("✓ Interactive report assembly works")
        
        # Save test output
        test_output_path = "test_interactive_report.html"
        ic.save_interactive_report_html(html_content, test_output_path)
        print(f"✓ Test report saved to {test_output_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Interactive report assembly failed: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    print("Running Interactive Weekly Review Tests")
    print("=" * 50)
    
    try:
        test_simple_chart_generation()
        success = test_interactive_report_assembly()
        
        if success:
            print("\n" + "=" * 50)
            print("✓ All tests passed!")
            print("The interactive weekly review system is ready for use.")
        else:
            print("\n" + "=" * 50)
            print("✗ Some tests failed. Check the output above.")
            
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()