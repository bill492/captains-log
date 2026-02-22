"""State management and catch-up logic."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from .config import STATE_FILE, TZ, CAPLOGS_DIR


def load_state() -> dict:
    """
    Load state from state.json.
    
    Returns:
        State dict with last_successful_end_time and pending_errors
    """
    if not STATE_FILE.exists():
        return {
            "last_successful_end_time": None,
            "pending_errors": []
        }
    
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load state file: {e}")
        return {
            "last_successful_end_time": None,
            "pending_errors": []
        }


def save_state(state: dict) -> None:
    """
    Save state to state.json.
    
    Args:
        state: State dict to save
    """
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error: Failed to save state file: {e}")
        raise


def update_state_success(state: dict, window_end: datetime) -> dict:
    """
    Update state after successful window processing.
    
    Args:
        state: Current state
        window_end: End time of successfully processed window
        
    Returns:
        Updated state
    """
    state["last_successful_end_time"] = window_end.isoformat()
    
    # Clear any pending error for this window
    state["pending_errors"] = [
        e for e in state.get("pending_errors", [])
        if e.get("window") != window_end.isoformat()
    ]
    
    return state


def update_state_error(state: dict, window_end: datetime, error: str) -> dict:
    """
    Update state after failed window processing.
    
    Args:
        state: Current state
        window_end: End time of failed window
        error: Error message
        
    Returns:
        Updated state
    """
    now = datetime.now(TZ)
    
    # Add to pending errors if not already there
    window_iso = window_end.isoformat()
    existing = [e for e in state.get("pending_errors", []) if e.get("window") == window_iso]
    
    if not existing:
        state.setdefault("pending_errors", []).append({
            "window": window_iso,
            "error": error,
            "timestamp": now.isoformat()
        })
    
    return state


def get_windows_since(
    start: datetime, 
    end: datetime, 
    interval_minutes: int = 30
) -> list[datetime]:
    """
    Generate all window end times from start to end.
    
    Args:
        start: Start time
        end: End time
        interval_minutes: Window interval in minutes
        
    Returns:
        List of window end times
    """
    windows = []
    current = start + timedelta(minutes=interval_minutes)
    
    while current <= end:
        windows.append(current)
        current += timedelta(minutes=interval_minutes)
    
    return windows


def get_windows_to_process(
    state: dict,
    now: Optional[datetime] = None,
    interval_minutes: int = 30
) -> list[datetime]:
    """
    Determine which windows need to be processed based on state.
    
    Args:
        state: Current state
        now: Current time (defaults to now)
        interval_minutes: Window interval in minutes
        
    Returns:
        List of window end times to process
    """
    if now is None:
        now = datetime.now(TZ)
    
    last_success = state.get("last_successful_end_time")
    
    if last_success is None:
        # First run ever - just process current window
        return [now]
    
    # Parse last success time
    try:
        last_dt = datetime.fromisoformat(last_success)
        
        # Convert to configured timezone if needed
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=TZ)
        else:
            last_dt = last_dt.astimezone(TZ)
        
        # Calculate all windows since last success
        windows = get_windows_since(last_dt, now, interval_minutes)
        
        # If no windows (last success was very recent), still process current
        if not windows:
            windows = [now]
        
        return windows
        
    except Exception as e:
        print(f"Warning: Failed to parse last success time: {e}")
        # Fall back to current window only
        return [now]


def get_previous_summaries(n: int = 2) -> list[str]:
    """
    Get last N successful run summaries for context.
    Pulls from today's caplogs first, then yesterday if needed.
    
    Args:
        n: Number of summaries to retrieve
        
    Returns:
        List of summary strings (most recent last)
    """
    summaries = []
    
    # Try today first
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    today_summaries = _get_summaries_from_date(today)
    summaries.extend(today_summaries)
    
    # If we need more, get from yesterday
    if len(summaries) < n:
        yesterday = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_summaries = _get_summaries_from_date(yesterday)
        summaries = yesterday_summaries + summaries
    
    # Return last N
    return summaries[-n:] if summaries else []


def _get_summaries_from_date(date: str) -> list[str]:
    """
    Get all successful run summaries from a specific date.
    
    Args:
        date: Date string (YYYY-MM-DD)
        
    Returns:
        List of summary strings
    """
    caplog_path = CAPLOGS_DIR / f"{date}.jsonl"
    
    if not caplog_path.exists():
        return []
    
    summaries = []
    
    try:
        with open(caplog_path) as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "ok" and "summary" in entry:
                        summaries.append(entry["summary"])
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    return summaries


def append_to_caplog(entry: dict, date: str = None) -> None:
    """
    Append a run entry to the daily caplog file.
    
    Args:
        entry: Run entry dict
        date: Date string (YYYY-MM-DD), defaults to today
    """
    if date is None:
        date = datetime.now(TZ).strftime("%Y-%m-%d")
    
    caplog_path = CAPLOGS_DIR / f"{date}.jsonl"
    
    # Create file if it doesn't exist
    if not caplog_path.exists():
        caplog_path.touch()
    
    # Append entry
    with open(caplog_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def cleanup_old_caplogs(days: int = 14) -> None:
    """
    Remove caplog files older than N days.
    
    Args:
        days: Retention period in days
    """
    cutoff = datetime.now(TZ) - timedelta(days=days)
    
    for path in CAPLOGS_DIR.glob("*.jsonl"):
        try:
            # Parse date from filename
            file_date = datetime.strptime(path.stem, "%Y-%m-%d")
            file_date = file_date.replace(tzinfo=TZ)
            
            if file_date < cutoff:
                path.unlink()
                print(f"Cleaned up old caplog: {path.name}")
        except Exception as e:
            print(f"Warning: Failed to process {path.name}: {e}")
