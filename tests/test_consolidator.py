"""Tests for consolidator.py - output merging and markdown rendering."""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.consolidator import merge_outputs, render_markdown, create_run_entry

TZ = ZoneInfo("America/New_York")


class TestMergeOutputs:
    """Test merging multiple summarizer outputs."""
    
    def test_merges_and_sorts_by_timestamp(self):
        """Entries from multiple outputs should be merged and sorted."""
        outputs = [
            {
                "entries": [
                    {"timestamp": "2026-01-30T15:00:00-05:00", "log": "Third"},
                ],
                "summary": "Batch 1"
            },
            {
                "entries": [
                    {"timestamp": "2026-01-30T14:00:00-05:00", "log": "First"},
                    {"timestamp": "2026-01-30T14:30:00-05:00", "log": "Second"},
                ],
                "summary": "Batch 2"
            }
        ]
        
        merged = merge_outputs(outputs)
        
        assert len(merged) == 3
        assert merged[0]["log"] == "First"
        assert merged[1]["log"] == "Second"
        assert merged[2]["log"] == "Third"
    
    def test_handles_empty_outputs(self):
        """Empty outputs should result in empty merge."""
        outputs = [{"entries": [], "summary": ""}]
        
        merged = merge_outputs(outputs)
        
        assert len(merged) == 0


class TestRenderMarkdown:
    """Test markdown rendering - critical for correct output format."""
    
    def test_renders_basic_entry(self):
        """Should render entry with timestamp header."""
        entries = [
            {
                "timestamp": "2026-01-30T14:30:00-05:00",
                "log": "Had a conversation with Bek about the project.",
                "remarks": None,
                "channel": "slack"
            }
        ]
        
        md = render_markdown(entries, "2026-01-30")
        
        assert "## 14:30" in md
        assert "Had a conversation with Bek" in md
    
    def test_renders_remarks_when_present(self):
        """Remarks should be included with bold label."""
        entries = [
            {
                "timestamp": "2026-01-30T14:30:00-05:00",
                "log": "Made a mistake.",
                "remarks": "Need to double-check next time.",
                "channel": "slack"
            }
        ]
        
        md = render_markdown(entries, "2026-01-30")
        
        assert "**Remarks:**" in md
        assert "Need to double-check" in md
    
    def test_no_remarks_when_none(self):
        """Remarks section should not appear when remarks is None."""
        entries = [
            {
                "timestamp": "2026-01-30T14:30:00-05:00",
                "log": "Normal entry.",
                "remarks": None,
                "channel": "slack"
            }
        ]
        
        md = render_markdown(entries, "2026-01-30")
        
        assert "**Remarks:**" not in md
    
    def test_empty_entries(self):
        """Empty entries should return empty string."""
        md = render_markdown([], "2026-01-30")
        
        assert md == ""


class TestCreateRunEntry:
    """Test run history entry creation."""
    
    def test_creates_ok_entry(self):
        """Should create complete entry for successful run."""
        ts = datetime(2026, 1, 30, 14, 30, tzinfo=TZ)
        
        entry = create_run_entry(
            timestamp=ts,
            status="ok",
            sessions=3,
            batches=1,
            entries=8,
            tokens_in=12500,
            tokens_out=1200,
            duration_ms=45000,
            summary="Discussed project plans"
        )
        
        assert entry["status"] == "ok"
        assert entry["sessions"] == 3
        assert entry["summary"] == "Discussed project plans"
    
    def test_creates_skip_entry(self):
        """Should create entry for skipped run."""
        ts = datetime(2026, 1, 30, 14, 30, tzinfo=TZ)
        
        entry = create_run_entry(
            timestamp=ts,
            status="skip",
            reason="no_activity",
            duration_ms=1200
        )
        
        assert entry["status"] == "skip"
        assert entry["reason"] == "no_activity"
    
    def test_creates_error_entry(self):
        """Should create entry for failed run."""
        ts = datetime(2026, 1, 30, 14, 30, tzinfo=TZ)
        
        entry = create_run_entry(
            timestamp=ts,
            status="error",
            error="API timeout",
            duration_ms=30000
        )
        
        assert entry["status"] == "error"
        assert entry["error"] == "API timeout"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
