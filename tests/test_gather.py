"""Tests for gather.py - session filtering and historical parsing."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.gather import should_include_session, read_transcript_in_window, infer_kind_from_key

TZ = ZoneInfo("America/New_York")


class TestShouldIncludeSession:
    """Test session filtering logic - critical for including sub-agents, excluding cron."""
    
    def test_includes_main_session(self):
        """Main sessions should always be included."""
        session = {"kind": "main", "key": "agent:main:main"}
        assert should_include_session(session) is True
    
    def test_includes_group_session(self):
        """Group sessions should always be included."""
        session = {"kind": "group", "key": "agent:main:slack:channel:abc123"}
        assert should_include_session(session) is True
    
    def test_includes_subagent_session(self):
        """Sub-agent sessions should be included."""
        session = {"kind": "other", "key": "agent:main:subagent:abc-123-def"}
        assert should_include_session(session) is True
    
    def test_excludes_cron_session(self):
        """Cron sessions should be excluded."""
        session = {"kind": "cron", "key": "cron:daily-task"}
        assert should_include_session(session) is False
    
    def test_excludes_hook_session(self):
        """Hook sessions should be excluded."""
        session = {"kind": "hook", "key": "hook:webhook-123"}
        assert should_include_session(session) is False
    
    def test_excludes_node_session(self):
        """Node sessions should be excluded."""
        session = {"kind": "node", "key": "node-raspberry-pi"}
        assert should_include_session(session) is False


class TestReadTranscriptInWindow:
    """Test historical transcript parsing - critical for migration."""
    
    def create_transcript(self, tmpdir: Path, entries: list[dict]) -> Path:
        """Helper to create a test transcript file."""
        transcript_path = tmpdir / "test-session.jsonl"
        with open(transcript_path, 'w') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        return transcript_path
    
    def test_extracts_messages_in_window(self):
        """Messages within the time window should be extracted."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            now = datetime.now(TZ)
            in_window = (now - timedelta(minutes=15)).isoformat()
            
            entries = [
                {"type": "session", "id": "test-123"},
                {
                    "type": "message",
                    "timestamp": in_window,
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Hello Bill"}]
                    }
                },
                {
                    "type": "message",
                    "timestamp": in_window,
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Hello! How can I help?"}]
                    }
                }
            ]
            
            path = self.create_transcript(tmpdir, entries)
            start = now - timedelta(minutes=30)
            end = now
            
            result = read_transcript_in_window(path, start, end)
            
            assert result is not None
            assert len(result["messages"]) == 2
            assert result["messages"][0]["role"] == "user"
            assert result["messages"][0]["content"] == "Hello Bill"
            assert result["messages"][1]["role"] == "assistant"
    
    def test_excludes_messages_outside_window(self):
        """Messages outside the time window should be excluded."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            now = datetime.now(TZ)
            old_time = (now - timedelta(hours=2)).isoformat()  # Outside 30min window
            
            entries = [
                {"type": "session", "id": "test-123"},
                {
                    "type": "message",
                    "timestamp": old_time,
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Old message"}]
                    }
                }
            ]
            
            path = self.create_transcript(tmpdir, entries)
            start = now - timedelta(minutes=30)
            end = now
            
            result = read_transcript_in_window(path, start, end)
            
            assert result is None  # No messages in window
    
    def test_skips_thinking_blocks(self):
        """Thinking blocks in content should be skipped, only text extracted."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            now = datetime.now(TZ)
            in_window = (now - timedelta(minutes=15)).isoformat()
            
            entries = [
                {"type": "session", "id": "test-123"},
                {
                    "type": "message",
                    "timestamp": in_window,
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "Let me think about this..."},
                            {"type": "text", "text": "Here is my answer."}
                        ]
                    }
                }
            ]
            
            path = self.create_transcript(tmpdir, entries)
            start = now - timedelta(minutes=30)
            end = now
            
            result = read_transcript_in_window(path, start, end)
            
            assert result is not None
            assert len(result["messages"]) == 1
            # Should only have the text, not the thinking
            assert "Here is my answer" in result["messages"][0]["content"]
            assert "Let me think" not in result["messages"][0]["content"]


class TestInferKindFromKey:
    """Test session kind inference from key patterns."""
    
    def test_infers_subagent(self):
        assert infer_kind_from_key("agent:main:subagent:abc-123") == "other"
    
    def test_infers_cron(self):
        assert infer_kind_from_key("cron:daily-task") == "cron"
    
    def test_infers_group(self):
        assert infer_kind_from_key("agent:main:slack:channel:abc") == "group"
    
    def test_infers_main_default(self):
        assert infer_kind_from_key("agent:main:main") == "main"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
