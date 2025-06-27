"""Test embedding_db.py functions against legacy db.py implementation."""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
import os, sys
from dotenv import load_dotenv
load_dotenv()

PROJECT_PATH = os.getenv('PROJECT_PATH', '/app')
sys.path.append(PROJECT_PATH)

import utils.db.db as db  # Legacy implementation
import utils.db.embedding_db as embedding_db  # New implementation

@pytest.fixture
def sample_embedding_data():
    """Create sample embedding data for testing."""
    return {
        "arxiv_codes": ["2401.00001", "2401.00002"],
        "doc_type": "abstract",
        "embedding_type": "gte",
        "embeddings": [
            np.random.rand(1024).tolist(),
            np.random.rand(1024).tolist()
        ]
    }

def assert_embeddings_equal(emb1: dict, emb2: dict, msg: str = ""):
    """Compare two embedding dictionaries thoroughly."""
    assert set(emb1.keys()) == set(emb2.keys()), f"{msg} - Different arxiv_codes"
    for code in emb1:
        np.testing.assert_array_almost_equal(
            np.array(emb1[code]),
            np.array(emb2[code]),
            decimal=6,
            err_msg=f"{msg} - Embeddings differ for {code}"
        )

## Read operation tests - using real DB

def test_load_embeddings():
    """Test load_embeddings against real database."""
    # Use a known embedding type and doc_type
    doc_type = "abstract"
    embedding_type = "gte"
    
    # First get some existing arxiv_codes from the DB
    with db.get_db_engine() as engine:
        existing_codes = db.get_pending_embeddings(doc_type, embedding_type, engine)[:2]
    
    if existing_codes:
        # Test with real arxiv codes
        legacy_embeddings = db.load_embeddings(existing_codes, doc_type, embedding_type)
        new_embeddings = embedding_db.load_embeddings(existing_codes, doc_type, embedding_type)
        assert_embeddings_equal(legacy_embeddings, new_embeddings, "load_embeddings() differs")

def test_get_pending_embeddings():
    """Test get_pending_embeddings against real database."""
    doc_type = "abstract"
    embedding_type = "gte"
    
    with db.get_db_engine() as engine:
        legacy_pending = db.get_pending_embeddings(doc_type, embedding_type, engine)
        new_pending = embedding_db.get_pending_embeddings(doc_type, embedding_type, engine)
        
        assert set(legacy_pending) == set(new_pending), "get_pending_embeddings() results differ"

## Write operation tests - using mocks

@patch('utils.db.embedding_db.execute_write_query')
@patch('sqlalchemy.engine.Engine.begin')
def test_store_embeddings_batch(mock_engine_begin, mock_new_write, sample_embedding_data):
    """Test store_embeddings_batch implementation matches legacy behavior."""
    # Setup
    mock_new_write.return_value = True
    mock_conn = MagicMock()
    mock_engine_begin.return_value.__enter__.return_value = mock_conn
    
    # Execute
    with db.get_db_engine() as engine:
        legacy_result = db.store_embeddings_batch(
            sample_embedding_data["arxiv_codes"],
            sample_embedding_data["doc_type"],
            sample_embedding_data["embedding_type"],
            sample_embedding_data["embeddings"],
            engine
        )
    
    with embedding_db.get_db_engine() as engine:
        new_result = embedding_db.store_embeddings_batch(
            sample_embedding_data["arxiv_codes"],
            sample_embedding_data["doc_type"],
            sample_embedding_data["embedding_type"],
            sample_embedding_data["embeddings"],
            engine
        )
    
    # Assert
    assert legacy_result == new_result, "store_embeddings_batch() return value differs"
    assert mock_new_write.called, "New implementation should call execute_write_query"
    assert mock_conn.execute.called, "Legacy implementation should call conn.execute" 