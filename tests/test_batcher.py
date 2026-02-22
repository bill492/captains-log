"""Tests for batcher.py - token-based batching logic."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.batcher import create_batches, get_batch_info


def make_session(key: str, message_count: int = 5, chars_per_msg: int = 100) -> dict:
    """Helper to create a test session with predictable token count."""
    return {
        "key": key,
        "kind": "main",
        "channel": "slack",
        "messages": [
            {"role": "user", "content": "x" * chars_per_msg}
            for _ in range(message_count)
        ]
    }


class TestCreateBatches:
    """Test batching logic - critical for handling large conversation volumes."""
    
    def test_single_batch_under_threshold(self):
        """Sessions under threshold should stay in one batch."""
        sessions = [
            make_session("session-1", message_count=5),
            make_session("session-2", message_count=5),
        ]
        
        batches = create_batches(sessions, max_tokens=50000)
        
        assert len(batches) == 1
        assert len(batches[0]) == 2
    
    def test_splits_when_over_threshold(self):
        """Should split into multiple batches when over threshold."""
        # Create sessions with lots of content
        sessions = [
            make_session(f"session-{i}", message_count=50, chars_per_msg=500)
            for i in range(5)
        ]
        
        batches = create_batches(sessions, max_tokens=5000)
        
        # Should have multiple batches
        assert len(batches) > 1
        
        # All sessions should be accounted for
        total_sessions = sum(len(b) for b in batches)
        assert total_sessions == 5
    
    def test_empty_input(self):
        """Empty session list should return empty batches."""
        batches = create_batches([], max_tokens=20000)
        
        assert len(batches) == 0
    
    def test_oversized_session_gets_own_batch(self):
        """A session exceeding the limit should get its own batch."""
        sessions = [
            make_session("small", message_count=5),
            make_session("huge", message_count=500, chars_per_msg=1000),  # Very large
            make_session("small2", message_count=5),
        ]
        
        batches = create_batches(sessions, max_tokens=5000)
        
        # The huge session should be in its own batch
        assert len(batches) >= 2


class TestGetBatchInfo:
    """Test batch statistics."""
    
    def test_empty_batches(self):
        """Empty batches should return zero stats."""
        info = get_batch_info([])
        
        assert info["num_batches"] == 0
        assert info["total_sessions"] == 0
        assert info["total_tokens"] == 0
    
    def test_calculates_stats(self):
        """Should calculate correct batch statistics."""
        batches = [
            [make_session("s1"), make_session("s2")],
            [make_session("s3")],
        ]
        
        info = get_batch_info(batches)
        
        assert info["num_batches"] == 2
        assert info["total_sessions"] == 3
        assert info["total_tokens"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
