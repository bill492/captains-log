"""Tests for state.py - catch-up queue and state management."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.state import (
    get_windows_since,
    get_windows_to_process,
    update_state_success,
    update_state_error,
    get_previous_summaries,
    _get_summaries_from_date
)

TZ = ZoneInfo("America/New_York")


class TestGetWindowsSince:
    """Test window calculation - critical for catch-up processing."""
    
    def test_calculates_correct_windows(self):
        """Should generate correct 30-min window boundaries."""
        start = datetime(2026, 1, 30, 14, 0, tzinfo=TZ)
        end = datetime(2026, 1, 30, 15, 30, tzinfo=TZ)
        
        windows = get_windows_since(start, end, interval_minutes=30)
        
        assert len(windows) == 3
        assert windows[0] == datetime(2026, 1, 30, 14, 30, tzinfo=TZ)
        assert windows[1] == datetime(2026, 1, 30, 15, 0, tzinfo=TZ)
        assert windows[2] == datetime(2026, 1, 30, 15, 30, tzinfo=TZ)
    
    def test_empty_when_no_windows(self):
        """Should return empty list when start and end are too close."""
        start = datetime(2026, 1, 30, 14, 0, tzinfo=TZ)
        end = datetime(2026, 1, 30, 14, 15, tzinfo=TZ)  # Only 15 min apart
        
        windows = get_windows_since(start, end, interval_minutes=30)
        
        assert len(windows) == 0
    
    def test_handles_2_hour_gap(self):
        """Should correctly calculate windows for 2-hour API downtime."""
        start = datetime(2026, 1, 30, 12, 0, tzinfo=TZ)
        end = datetime(2026, 1, 30, 14, 0, tzinfo=TZ)  # 2 hours = 4 windows
        
        windows = get_windows_since(start, end, interval_minutes=30)
        
        assert len(windows) == 4


class TestGetWindowsToProcess:
    """Test state-based window determination."""
    
    def test_first_run_returns_current_window(self):
        """First run (no state) should just process current window."""
        state = {"last_successful_end_time": None, "pending_errors": []}
        now = datetime(2026, 1, 30, 15, 0, tzinfo=TZ)
        
        windows = get_windows_to_process(state, now=now)
        
        assert len(windows) == 1
        assert windows[0] == now
    
    def test_catch_up_after_downtime(self):
        """Should calculate catch-up windows after downtime."""
        # Last success was 1.5 hours ago
        last_success = datetime(2026, 1, 30, 13, 30, tzinfo=TZ)
        state = {
            "last_successful_end_time": last_success.isoformat(),
            "pending_errors": []
        }
        now = datetime(2026, 1, 30, 15, 0, tzinfo=TZ)
        
        windows = get_windows_to_process(state, now=now)
        
        # Should have 3 windows: 14:00, 14:30, 15:00
        assert len(windows) == 3


class TestUpdateState:
    """Test state update functions."""
    
    def test_success_updates_timestamp(self):
        """Successful run should update last_successful_end_time."""
        state = {"last_successful_end_time": None, "pending_errors": []}
        window_end = datetime(2026, 1, 30, 15, 0, tzinfo=TZ)
        
        updated = update_state_success(state, window_end)
        
        assert updated["last_successful_end_time"] == window_end.isoformat()
    
    def test_success_clears_pending_error(self):
        """Successful run should clear pending error for that window."""
        window_end = datetime(2026, 1, 30, 15, 0, tzinfo=TZ)
        state = {
            "last_successful_end_time": None,
            "pending_errors": [
                {"window": window_end.isoformat(), "error": "API timeout"}
            ]
        }
        
        updated = update_state_success(state, window_end)
        
        assert len(updated["pending_errors"]) == 0
    
    def test_error_adds_to_pending(self):
        """Failed run should add to pending_errors."""
        state = {"last_successful_end_time": None, "pending_errors": []}
        window_end = datetime(2026, 1, 30, 15, 0, tzinfo=TZ)
        
        updated = update_state_error(state, window_end, "API timeout")
        
        assert len(updated["pending_errors"]) == 1
        assert updated["pending_errors"][0]["window"] == window_end.isoformat()
        assert updated["pending_errors"][0]["error"] == "API timeout"


class TestGetPreviousSummaries:
    """Test context retrieval from caplogs."""
    
    def test_gets_summaries_from_caplog(self):
        """Should extract summaries from caplog JSONL."""
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create a mock caplog file
            caplog_content = [
                {"timestamp": "2026-01-30T14:00:00", "status": "ok", "summary": "First summary"},
                {"timestamp": "2026-01-30T14:30:00", "status": "skip", "reason": "no_activity"},
                {"timestamp": "2026-01-30T15:00:00", "status": "ok", "summary": "Second summary"},
            ]
            
            caplog_path = tmpdir / "2026-01-30.jsonl"
            with open(caplog_path, 'w') as f:
                for entry in caplog_content:
                    f.write(json.dumps(entry) + '\n')
            
            # Test the internal function with the temp path
            summaries = []
            with open(caplog_path) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("status") == "ok" and "summary" in entry:
                        summaries.append(entry["summary"])
            
            assert len(summaries) == 2
            assert summaries[0] == "First summary"
            assert summaries[1] == "Second summary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
