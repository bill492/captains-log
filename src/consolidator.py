"""Consolidate GPT-5.2 outputs and render to markdown."""

from datetime import datetime
from pathlib import Path
from .config import MEMORY_DIR, TZ


def merge_outputs(outputs: list[dict]) -> list[dict]:
    """
    Merge multiple summarizer outputs and sort by timestamp.
    
    Args:
        outputs: List of output dicts from GPT-5.2
        
    Returns:
        Sorted list of all entries
    """
    all_entries = []
    
    for output in outputs:
        entries = output.get("entries", [])
        all_entries.extend(entries)
    
    # Sort by timestamp
    all_entries.sort(key=lambda e: e.get("timestamp", ""))
    
    return all_entries


def render_markdown(entries: list[dict], date: str) -> str:
    """
    Render entries to Captain's Log markdown format.
    
    Args:
        entries: List of entry dicts
        date: Date string (YYYY-MM-DD)
        
    Returns:
        Markdown formatted string
    """
    if not entries:
        return ""
    
    lines = []
    
    for entry in entries:
        timestamp = entry.get("timestamp", "")
        log = entry.get("log", "")
        remarks = entry.get("remarks")
        
        # Extract time from timestamp and convert to EST
        try:
            from zoneinfo import ZoneInfo
            UTC = ZoneInfo("UTC")
            
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Convert to EST timezone
            if dt.tzinfo is None:
                # Assume naive timestamps are UTC, then convert to EST
                dt = dt.replace(tzinfo=UTC).astimezone(TZ)
            else:
                dt = dt.astimezone(TZ)
            
            time_str = dt.strftime("%H:%M EST")
        except Exception:
            time_str = timestamp
        
        # Build entry
        lines.append(f"## {time_str}")
        lines.append(log)
        
        if remarks:
            lines.append(f"\n**Remarks:** {remarks}")
        
        lines.append("\n---\n")
    
    return "\n".join(lines)


def append_to_daily_file(markdown: str, date: str) -> None:
    """
    Append to memory/YYYY-MM-DD.md, creating if needed.
    
    Args:
        markdown: Markdown content to append
        date: Date string (YYYY-MM-DD)
    """
    if not markdown:
        return
    
    file_path = MEMORY_DIR / f"{date}.md"
    
    # Create file with header if it doesn't exist
    if not file_path.exists():
        header = f"# Captain's Log — {date}\n\n"
        file_path.write_text(header, encoding='utf-8')
    
    # Append content
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(markdown)


def get_daily_file_path(date: str = None) -> Path:
    """
    Get path to daily memory file.
    
    Args:
        date: Date string (YYYY-MM-DD), defaults to today
        
    Returns:
        Path to daily file
    """
    if date is None:
        date = datetime.now(TZ).strftime("%Y-%m-%d")
    
    return MEMORY_DIR / f"{date}.md"


def create_run_entry(
    timestamp: datetime,
    status: str,
    sessions: int = 0,
    batches: int = 0,
    entries: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
    summary: str = "",
    error: str = None,
    reason: str = None
) -> dict:
    """
    Create a run history entry for caplogs.
    
    Args:
        timestamp: Run timestamp
        status: "ok", "skip", or "error"
        sessions: Number of sessions processed
        batches: Number of batches created
        entries: Number of log entries created
        tokens_in: Input tokens used
        tokens_out: Output tokens used
        duration_ms: Run duration in milliseconds
        summary: Summary of this run
        error: Error message if status == "error"
        reason: Reason if status == "skip"
        
    Returns:
        Dict for JSONL logging
    """
    entry = {
        "timestamp": timestamp.isoformat(),
        "status": status
    }
    
    if status == "ok":
        entry.update({
            "sessions": sessions,
            "batches": batches,
            "entries": entries,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
            "summary": summary
        })
    elif status == "error":
        entry.update({
            "error": error,
            "duration_ms": duration_ms
        })
    elif status == "skip":
        entry.update({
            "reason": reason,
            "duration_ms": duration_ms
        })
    
    return entry
