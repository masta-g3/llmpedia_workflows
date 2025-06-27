"""Test paper_db.py functions against legacy db.py implementation."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

import utils.db.db as db  # Legacy implementation
import utils.db.paper_db as paper_db  # New implementation

def assert_dataframes_equal(df1: pd.DataFrame, df2: pd.DataFrame, msg: str = ""):
    """Compare two dataframes thoroughly."""
    # Check if both are empty
    if df1.empty and df2.empty:
        return True
        
    # Check basic properties
    assert df1.shape == df2.shape, f"{msg} - Different shapes: {df1.shape} vs {df2.shape}"
    assert list(df1.columns) == list(df2.columns), f"{msg} - Different columns"
    assert df1.index.equals(df2.index), f"{msg} - Different indices"
    
    # Check content (handling NaN equality)
    pd.testing.assert_frame_equal(df1, df2, check_dtype=False)

def test_load_arxiv():
    """Test load_arxiv with and without arxiv_code."""
    # Test without arxiv_code
    legacy_df = db.load_arxiv()
    new_df = paper_db.load_arxiv()
    assert_dataframes_equal(legacy_df, new_df, "load_arxiv() differs")
    
    # Test with specific arxiv_code
    arxiv_code = legacy_df.index[0]  # Use first available code
    legacy_df = db.load_arxiv(arxiv_code)
    new_df = paper_db.load_arxiv(arxiv_code)
    assert_dataframes_equal(legacy_df, new_df, f"load_arxiv({arxiv_code}) differs")

def test_load_summaries():
    """Test load_summaries."""
    legacy_df = db.load_summaries()
    new_df = paper_db.load_summaries()
    assert_dataframes_equal(legacy_df, new_df, "load_summaries() differs")

def test_load_recursive_summaries():
    """Test load_recursive_summaries with both drop_tstp options."""
    # Test with drop_tstp=True
    legacy_df = db.load_recursive_summaries(drop_tstp=True)
    new_df = paper_db.load_recursive_summaries(drop_tstp=True)
    assert_dataframes_equal(legacy_df, new_df, "load_recursive_summaries(drop_tstp=True) differs")
    
    # Test with drop_tstp=False
    legacy_df = db.load_recursive_summaries(drop_tstp=False)
    new_df = paper_db.load_recursive_summaries(drop_tstp=False)
    assert_dataframes_equal(legacy_df, new_df, "load_recursive_summaries(drop_tstp=False) differs")

def test_load_bullet_list_summaries():
    """Test load_bullet_list_summaries."""
    legacy_df = db.load_bullet_list_summaries()
    new_df = paper_db.load_bullet_list_summaries()
    assert_dataframes_equal(legacy_df, new_df, "load_bullet_list_summaries() differs")

def test_load_summary_notes():
    """Test load_summary_notes."""
    legacy_df = db.load_summary_notes()
    new_df = paper_db.load_summary_notes()
    assert_dataframes_equal(legacy_df, new_df, "load_summary_notes() differs")

def test_load_summary_markdown():
    """Test load_summary_markdown."""
    legacy_df = db.load_summary_markdown()
    new_df = paper_db.load_summary_markdown()
    assert_dataframes_equal(legacy_df, new_df, "load_summary_markdown() differs")

def test_load_topics():
    """Test load_topics."""
    legacy_df = db.load_topics()
    new_df = paper_db.load_topics()
    assert_dataframes_equal(legacy_df, new_df, "load_topics() differs")

def test_load_similar_documents():
    """Test load_similar_documents."""
    legacy_df = db.load_similar_documents()
    new_df = paper_db.load_similar_documents()
    assert_dataframes_equal(legacy_df, new_df, "load_similar_documents() differs")

def test_load_citations():
    """Test load_citations with and without arxiv_code."""
    # Test without arxiv_code
    legacy_df = db.load_citations()
    new_df = paper_db.load_citations()
    assert_dataframes_equal(legacy_df, new_df, "load_citations() differs")
    
    # Test with specific arxiv_code
    if not legacy_df.empty:
        arxiv_code = legacy_df.index[0]  # Use first available code
        legacy_df = db.load_citations(arxiv_code)
        new_df = paper_db.load_citations(arxiv_code)
        assert_dataframes_equal(legacy_df, new_df, f"load_citations({arxiv_code}) differs")

def test_load_repositories():
    """Test load_repositories with and without arxiv_code."""
    # Test without arxiv_code
    legacy_df = db.load_repositories()
    new_df = paper_db.load_repositories()
    assert_dataframes_equal(legacy_df, new_df, "load_repositories() differs")
    
    # Test with specific arxiv_code
    if not legacy_df.empty:
        arxiv_code = legacy_df.index[0]  # Use first available code
        legacy_df = db.load_repositories(arxiv_code)
        new_df = paper_db.load_repositories(arxiv_code)
        assert_dataframes_equal(legacy_df, new_df, f"load_repositories({arxiv_code}) differs")

def test_get_extended_content():
    """Test get_extended_content."""
    # Get a valid arxiv_code from arxiv_details
    arxiv_df = db.load_arxiv()
    if not arxiv_df.empty:
        arxiv_code = arxiv_df.index[0]
        legacy_df = db.get_extended_content(arxiv_code)
        new_df = paper_db.get_extended_content(arxiv_code)
        assert_dataframes_equal(legacy_df, new_df, f"get_extended_content({arxiv_code}) differs")

def test_get_weekly_summary_inputs():
    """Test get_weekly_summary_inputs."""
    # Use current date for testing
    date = datetime.now().strftime("%Y-%m-%d")
    legacy_df = db.get_weekly_summary_inputs(date)
    new_df = paper_db.get_weekly_summary_inputs(date)
    assert_dataframes_equal(legacy_df, new_df, f"get_weekly_summary_inputs({date}) differs")

def test_get_weekly_repos():
    """Test get_weekly_repos."""
    # Use current date for testing
    date = datetime.now().strftime("%Y-%m-%d")
    legacy_df = db.get_weekly_repos(date)
    new_df = paper_db.get_weekly_repos(date)
    assert_dataframes_equal(legacy_df, new_df, f"get_weekly_repos({date}) differs")

def test_get_papers_since():
    """Test get_papers_since."""
    # Test with 24 hours ago
    cutoff_time = datetime.now() - timedelta(hours=24)
    legacy_df = db.get_papers_since(cutoff_time)
    new_df = paper_db.get_papers_since(cutoff_time)
    assert_dataframes_equal(legacy_df, new_df, f"get_papers_since({cutoff_time}) differs") 