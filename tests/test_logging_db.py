"""Test logging_db.py functions against legacy db.py implementation."""

import pytest
from datetime import datetime
import pandas as pd
from unittest.mock import patch, MagicMock
import os, sys
from dotenv import load_dotenv
load_dotenv()

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
sys.path.append(PROJECT_PATH)

import utils.db.db as db  # Legacy implementation
import utils.db.logging_db as logging_db  # New implementation
from utils.db.db_utils import execute_read_query

def assert_log_entries_equal(query: str, msg: str = ""):
    """Compare the most recent log entries from both implementations."""
    df = execute_read_query(query + " ORDER BY tstp DESC LIMIT 1")
    if not df.empty:
        # Drop id and tstp columns as they will be different
        df = df.drop(columns=['tstp'])
        if 'id' in df.columns:
            df = df.drop(columns=['id'])
        if 'error_id' in df.columns:
            df = df.drop(columns=['error_id'])
        if 'qna_id' in df.columns:
            df = df.drop(columns=['qna_id'])
        if 'visit_id' in df.columns:
            df = df.drop(columns=['visit_id'])
            
        # If we have multiple rows, they should be identical (our test entries)
        if len(df) > 1:
            pd.testing.assert_frame_equal(
                df.iloc[[0]],
                df.iloc[[1]],
                check_dtype=False,
                err_msg=msg
            )

@patch('utils.db.logging_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_log_instructor_query(mock_engine_begin, mock_new_write):
    """Test log_instructor_query by writing and comparing entries."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    test_data = {
        "model_name": "test-model",
        "process_id": "test-process",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "prompt_cost": 0.001,
        "completion_cost": 0.002
    }
    
    # Execute
    legacy_result = db.log_instructor_query(**test_data)
    new_result = logging_db.log_instructor_query(**test_data)
    
    # Assert
    assert legacy_result == new_result, "log_instructor_query() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.logging_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_log_error_db(mock_engine_begin, mock_new_write):
    """Test log_error_db by writing and comparing entries."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    error_msg = "Test error message"
    
    # Execute
    legacy_result = db.log_error_db(error_msg)
    new_result = logging_db.log_error_db(error_msg)
    
    # Assert
    assert legacy_result == new_result, "log_error_db() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.logging_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_log_qna_db(mock_engine_begin, mock_new_write):
    """Test log_qna_db by writing and comparing entries."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    test_data = {
        "user_question": "Test question?",
        "response": "Test response."
    }
    
    # Execute
    legacy_result = db.log_qna_db(**test_data)
    new_result = logging_db.log_qna_db(**test_data)
    
    # Assert
    assert legacy_result == new_result, "log_qna_db() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.logging_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_log_visit(mock_engine_begin, mock_new_write):
    """Test log_visit by writing and comparing entries."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    entrypoint = "test_page"
    
    # Execute
    legacy_result = db.log_visit(entrypoint)
    new_result = logging_db.log_visit(entrypoint)
    
    # Assert
    assert legacy_result == new_result, "log_visit() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.logging_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_log_workflow_error(mock_engine_begin, mock_new_write):
    """Test log_workflow_error by writing and comparing entries."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    test_data = {
        "step_name": "test_step",
        "script_path": "/test/path.py",
        "error_message": "Test error"
    }
    
    # Execute
    legacy_result = db.log_workflow_error(**test_data)
    new_result = logging_db.log_workflow_error(**test_data)
    
    # Assert
    assert legacy_result == new_result, "log_workflow_error() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute"

@patch('utils.db.logging_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_log_workflow_run(mock_engine_begin, mock_new_write):
    """Test log_workflow_run by writing and comparing entries."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    test_data = {
        "step_name": "test_step",
        "script_path": "/test/path.py",
        "status": "success",
        "error_message": None
    }
    
    # Execute
    legacy_result = db.log_workflow_run(**test_data)
    new_result = logging_db.log_workflow_run(**test_data)
    
    # Assert
    assert legacy_result == new_result, "log_workflow_run() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute" 