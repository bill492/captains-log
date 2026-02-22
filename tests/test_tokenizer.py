"""Tests for tokenizer module."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tokenizer import count_tokens, estimate_session_tokens, estimate_batch_tokens


def test_count_tokens():
    """Test basic token counting."""
    text = "Hello, world!"
    tokens = count_tokens(text)
    assert tokens > 0
    assert isinstance(tokens, int)


def test_estimate_session_tokens():
    """Test session token estimation."""
    session = {
        "key": "agent:main:main",
        "channel": "slack",
        "kind": "main",
        "displayName": "",
        "messages": [
            {
                "role": "user",
                "content": "Hello, how are you?",
                "timestamp": "2026-01-30T14:30:00-05:00"
            },
            {
                "role": "assistant",
                "content": "I'm doing well, thank you!",
                "timestamp": "2026-01-30T14:30:05-05:00"
            }
        ]
    }
    
    tokens = estimate_session_tokens(session)
    assert tokens > 0
    assert isinstance(tokens, int)


def test_estimate_batch_tokens():
    """Test batch token estimation."""
    sessions = [
        {
            "key": "session1",
            "channel": "slack",
            "kind": "main",
            "messages": [
                {"role": "user", "content": "Test message"}
            ]
        },
        {
            "key": "session2",
            "channel": "telegram",
            "kind": "group",
            "messages": [
                {"role": "user", "content": "Another test message"}
            ]
        }
    ]
    
    tokens = estimate_batch_tokens(sessions)
    assert tokens > 0
    assert isinstance(tokens, int)


def test_empty_session():
    """Test with empty session."""
    session = {
        "key": "test",
        "messages": []
    }
    
    tokens = estimate_session_tokens(session)
    assert tokens >= 0


if __name__ == "__main__":
    test_count_tokens()
    test_estimate_session_tokens()
    test_estimate_batch_tokens()
    test_empty_session()
    print("All tokenizer tests passed")
