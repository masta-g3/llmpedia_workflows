"""Test tweet_db.py functions against legacy db.py implementation."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
import logging
from unittest.mock import patch, MagicMock
import os, sys
from dotenv import load_dotenv
load_dotenv()

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
sys.path.append(PROJECT_PATH)

import utils.db.db as db  # Legacy implementation
import utils.db.tweet_db as tweet_db  # New implementation

def assert_dataframes_equal(df1: pd.DataFrame, df2: pd.DataFrame, msg: str = ""):
    """Compare two dataframes thoroughly."""
    # Check if both are empty
    if df1.empty and df2.empty:
        return True
        
    # Check basic properties
    assert df1.shape == df2.shape, f"{msg} - Different shapes: {df1.shape} vs {df2.shape}"
    assert list(df1.columns) == list(df2.columns), f"{msg} - Different columns"
    
    # Check content (handling NaN equality)
    pd.testing.assert_frame_equal(df1, df2, check_dtype=False)

## Read operation tests - using real DB

def test_read_tweets():
    """Test read_tweets with various parameters."""
    # Test without parameters
    legacy_df = db.read_tweets()
    new_df = tweet_db.read_tweets()
    assert_dataframes_equal(legacy_df, new_df, "read_tweets() differs")
    
    if not legacy_df.empty:
        # Test with arxiv_code
        arxiv_code = legacy_df['arxiv_code'].iloc[0]
        legacy_df = db.read_tweets(arxiv_code=arxiv_code)
        new_df = tweet_db.read_tweets(arxiv_code=arxiv_code)
        assert_dataframes_equal(legacy_df, new_df, f"read_tweets(arxiv_code={arxiv_code}) differs")
        
        # Test with date range
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        legacy_df = db.read_tweets(start_date=start_date, end_date=end_date)
        new_df = tweet_db.read_tweets(start_date=start_date, end_date=end_date)
        assert_dataframes_equal(legacy_df, new_df, f"read_tweets(date_range) differs")

def test_read_last_n_tweet_analyses():
    """Test read_last_n_tweet_analyses."""
    n = 5
    legacy_df = db.read_last_n_tweet_analyses(n)
    new_df = tweet_db.read_last_n_tweet_analyses(n)
    assert_dataframes_equal(legacy_df, new_df, f"read_last_n_tweet_analyses({n}) differs")

def test_read_tweet_replies():
    """Test read_tweet_replies with various parameters."""
    # Test without parameters
    legacy_df = db.read_tweet_replies()
    new_df = tweet_db.read_tweet_replies()
    assert_dataframes_equal(legacy_df, new_df, "read_tweet_replies() differs")
    
    # Test with date range
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    legacy_df = db.read_tweet_replies(start_date=start_date, end_date=end_date)
    new_df = tweet_db.read_tweet_replies(start_date=start_date, end_date=end_date)
    assert_dataframes_equal(legacy_df, new_df, f"read_tweet_replies(date_range) differs")

## Write operation tests - using mocks

@patch('utils.db.tweet_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_store_tweets(mock_engine_begin, mock_new_write):
    """Test store_tweets implementation matches legacy behavior."""
    # Setup
    logger = logging.getLogger(__name__)
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    sample_tweet = {
        "text": "Test tweet",
        "author": "Test Author",
        "username": "testuser",
        "link": f"https://twitter.com/test/{datetime.now().timestamp()}",
        "tweet_timestamp": datetime.now(),
        "reply_count": 0,
        "repost_count": 0,
        "like_count": 0,
        "view_count": 0,
        "bookmark_count": 0,
        "has_media": False,
        "is_verified": False,
        "arxiv_code": "2401.00001"
    }
    
    # Execute
    with db.get_db_engine() as engine:
        legacy_result = db.store_tweets([sample_tweet], logger, engine)
    with tweet_db.get_db_engine() as engine:
        new_result = tweet_db.store_tweets([sample_tweet], logger, engine)
    
    # Assert
    assert legacy_result == new_result, "store_tweets() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.tweet_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_store_tweet_analysis(mock_engine_begin, mock_new_write):
    """Test store_tweet_analysis implementation matches legacy behavior."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    min_date = datetime.now() - timedelta(hours=1)
    max_date = datetime.now()
    unique_count = 10
    thinking_process = "Test thinking process"
    response = "Test response"
    
    # Execute
    legacy_result = db.store_tweet_analysis(min_date, max_date, unique_count, thinking_process, response)
    new_result = tweet_db.store_tweet_analysis(min_date, max_date, unique_count, thinking_process, response)
    
    # Assert
    assert legacy_result == new_result, "store_tweet_analysis() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.tweet_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_store_tweet_reply(mock_engine_begin, mock_new_write):
    """Test store_tweet_reply implementation matches legacy behavior."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    selected_tweet = "Test tweet"
    response = "Test response"
    meta_data = {"test_key": "test_value"}
    
    # Execute
    legacy_result = db.store_tweet_reply(selected_tweet, response, meta_data)
    new_result = tweet_db.store_tweet_reply(selected_tweet, response, meta_data)
    
    # Assert
    assert legacy_result == new_result, "store_tweet_reply() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute" 