#!/usr/bin/env python3
"""Full migration script - process all windows from state to now using historical mode."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 encoding for transcripts with unicode
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from src.config import TZ
from src.state import load_state, save_state, update_state_success, update_state_error
from main import process_window

def migrate():
    """Run full migration from state.last_successful_end_time to now."""
    state = load_state()
    
    # Parse last successful time
    last_time_str = state.get("last_successful_end_time")
    if last_time_str:
        last_time = datetime.fromisoformat(last_time_str)
    else:
        # Default to 7 days ago
        last_time = datetime.now(TZ) - timedelta(days=7)
    
    now = datetime.now(TZ)
    window_minutes = 30
    
    # Build list of windows to process
    current = last_time + timedelta(minutes=window_minutes)
    windows = []
    while current <= now:
        windows.append(current)
        current += timedelta(minutes=window_minutes)
    
    print(f"Migration: {len(windows)} windows from {last_time.isoformat()} to {now.isoformat()}")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for i, window_end in enumerate(windows):
        print(f"\n[{i+1}/{len(windows)}] Window: {window_end.isoformat()}")
        
        try:
            result = process_window(
                end_time=window_end,
                window_minutes=window_minutes,
                mode="historical",  # Read from transcripts
                dry_run=False
            )
            
            if result["status"] == "ok":
                success_count += 1
                state = update_state_success(state, window_end)
            elif result["status"] == "skip":
                skip_count += 1
                state = update_state_success(state, window_end)
            else:
                error_count += 1
                state = update_state_error(state, window_end, result.get("error", "Unknown"))
            
            save_state(state)
            
        except Exception as e:
            print(f"Error: {e}")
            error_count += 1
            state = update_state_error(state, window_end, str(e))
            save_state(state)
    
    print(f"\n{'='*60}")
    print(f"Migration complete:")
    print(f"  Success: {success_count}")
    print(f"  Skipped: {skip_count}")
    print(f"  Errors:  {error_count}")
    print(f"  Total:   {len(windows)}")

if __name__ == "__main__":
    migrate()
