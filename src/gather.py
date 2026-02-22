"""Gather session data from OpenClaw API or JSONL transcripts."""

import json
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from .config import (
    GATEWAY_URL, GATEWAY_TOKEN, ACTIVE_MINUTES, MESSAGE_LIMIT,
    SESSION_KINDS, SESSIONS_DIR, TZ, CONTEXT_MESSAGES
)


class GatherError(Exception):
    """Error during session gathering."""
    pass


def gather_sessions(
    end_time: Optional[datetime] = None,
    window_minutes: int = ACTIVE_MINUTES,
    mode: str = "live",
    message_limit: int = MESSAGE_LIMIT,
    kinds: list[str] = None
) -> list[dict]:
    """
    Fetch all sessions with activity in the specified window.
    
    Args:
        end_time: End of window (defaults to now, ignored in live mode)
        window_minutes: Window size in minutes (default 30)
        mode: "live" uses API, "historical" reads transcripts
        message_limit: Max messages per session
        kinds: Session types to include (default from config)
    
    Returns:
        List of session dicts with messages included.
        Empty list if no activity.
    
    Raises:
        GatherError: If API call or transcript read fails
    """
    if kinds is None:
        kinds = SESSION_KINDS
    
    if mode == "live":
        return _gather_live(window_minutes, message_limit, kinds)
    else:
        return _gather_historical(end_time, window_minutes, message_limit, kinds)


def should_include_session(session: dict) -> bool:
    """
    Determine if a session should be included in Captain's Logs.
    Includes: main, group, and sub-agent sessions.
    Excludes: cron, hook, node sessions.
    
    Args:
        session: Session dict
        
    Returns:
        True if session should be included
    """
    kind = session.get("kind", "")
    key = session.get("key", "")
    
    # Always include main and group
    if kind in ["main", "group"]:
        return True
    
    # Include sub-agent sessions (pattern: agent:*:subagent:*)
    if "subagent:" in key:
        return True
    
    # Include "other" kind if it looks like a sub-agent
    if kind == "other" and ("subagent" in key.lower() or "spawn" in key.lower()):
        return True
    
    # Exclude cron, hook, node
    if kind in ["cron", "hook", "node"]:
        return False
    
    # Default: include
    return True


def _gather_live(
    window_minutes: int,
    message_limit: int,
    kinds: list[str]
) -> list[dict]:
    """
    Gather via OpenClaw sessions_list API.
    
    Args:
        window_minutes: Window size in minutes
        message_limit: Max messages per session
        kinds: Session types to include
        
    Returns:
        List of session dicts with messages
        
    Raises:
        GatherError: If API call fails
    """
    try:
        response = call_gateway_api("sessions.list", {
            "activeMinutes": window_minutes,
            "messageLimit": message_limit,
            "kinds": kinds
        })
        
        sessions = response.get("sessions", [])
        
        # Filter to include sub-agents and exclude unwanted types
        filtered = [s for s in sessions if should_include_session(s)]
        
        return filtered
        
    except Exception as e:
        raise GatherError(f"Failed to gather sessions via API: {e}")


def _gather_historical(
    end_time: Optional[datetime],
    window_minutes: int,
    message_limit: int,
    kinds: list[str]
) -> list[dict]:
    """
    Gather by reading JSONL transcripts directly.
    Filters messages within the time window.
    
    Args:
        end_time: End of window (defaults to now)
        window_minutes: Window size in minutes
        message_limit: Max messages per session
        kinds: Session types to include
        
    Returns:
        List of session dicts with filtered messages
        
    Raises:
        GatherError: If transcript reading fails
    """
    try:
        end = end_time or datetime.now(TZ)
        start = end - timedelta(minutes=window_minutes)
        
        sessions = []
        
        if not SESSIONS_DIR.exists():
            raise GatherError(f"Sessions directory not found: {SESSIONS_DIR}")
        
        for transcript_path in SESSIONS_DIR.glob("*.jsonl"):
            session_data = read_transcript_in_window(
                transcript_path, start, end, message_limit
            )
            
            if session_data and session_data.get("messages"):
                # Filter to requested kinds
                if should_include_session(session_data):
                    if session_data.get("kind") in kinds or "other" in kinds:
                        sessions.append(session_data)
        
        return sessions
        
    except GatherError:
        raise
    except Exception as e:
        raise GatherError(f"Failed to gather historical sessions: {e}")


def read_transcript_in_window(
    path: Path, 
    start: datetime, 
    end: datetime,
    limit: int = MESSAGE_LIMIT,
    context_count: int = CONTEXT_MESSAGES
) -> Optional[dict]:
    """
    Read a transcript file and extract messages within time window,
    plus context messages from before the window.
    
    Args:
        path: Path to JSONL transcript
        start: Window start time
        end: Window end time
        limit: Max messages to include in window
        context_count: Number of messages before window to include for context
        
    Returns:
        Session dict with 'messages' (in window) and 'context' (before window),
        or None if no messages in window
    """
    all_messages = []  # All messages with timestamps
    session_info = {}
    
    try:
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                    
                try:
                    entry = json.loads(line)
                    entry_type = entry.get("type", "")
                    
                    # Extract session metadata from session entry
                    if entry_type == "session" and not session_info:
                        session_info = {
                            "key": entry.get("id", path.stem),
                            "kind": infer_kind_from_key(entry.get("id", path.stem)),
                            "channel": "unknown",
                            "displayName": ""
                        }
                        continue
                    
                    # Skip non-message entries
                    if entry_type != "message":
                        continue
                    
                    # Parse timestamp
                    ts = parse_timestamp(entry.get("timestamp"))
                    if not ts:
                        continue
                    
                    # Extract message from nested structure
                    msg_data = entry.get("message", {})
                    role = msg_data.get("role", "unknown")
                    content_blocks = msg_data.get("content", [])
                    
                    # Extract text content from content blocks
                    # Skip tool_use, tool_result, and thinking blocks
                    text_parts = []
                    for block in content_blocks:
                        if isinstance(block, dict):
                            block_type = block.get("type", "")
                            # Only include text blocks, skip tool-related and thinking
                            if block_type == "text":
                                text = block.get("text", "")
                                # Filter out TOOLRESULT lines from the text
                                filtered_lines = []
                                for line in text.split("\n"):
                                    # Skip tool output markers and their content
                                    if any(marker in line for marker in [
                                        "TOOLRESULT:", "TOOLCALL:", "TOOL_USE:",
                                        "Process still running", 
                                        "Successfully replaced text",
                                        "Successfully wrote"
                                    ]):
                                        continue
                                    # Skip lines that look like table borders or raw CLI output
                                    if line.strip().startswith("â") or "ââ" in line:
                                        continue
                                    filtered_lines.append(line)
                                filtered_text = "\n".join(filtered_lines).strip()
                                if filtered_text:
                                    text_parts.append(filtered_text)
                            # Skip: tool_use, tool_result, thinking, thinkingSignature
                        elif isinstance(block, str):
                            # Filter TOOLRESULT from string blocks too
                            if "TOOLRESULT:" not in block and "TOOLCALL:" not in block:
                                text_parts.append(block)
                    
                    content = "\n".join(text_parts)
                    
                    if content:  # Only add if there's actual text content
                        message = {
                            "role": role,
                            "content": content,
                            "timestamp": entry.get("timestamp"),
                            "_parsed_ts": ts  # Keep parsed timestamp for filtering
                        }
                        all_messages.append(message)
                        
                except json.JSONDecodeError:
                    continue
        
        # Separate into context (before window) and window messages
        # Filter out messages with None timestamps (parse failures)
        messages_before = [m for m in all_messages if m["_parsed_ts"] is not None and m["_parsed_ts"] < start]
        messages_in_window = [m for m in all_messages if m["_parsed_ts"] is not None and start <= m["_parsed_ts"] <= end]
        
        # No new messages in window = nothing to process
        if not messages_in_window:
            return None
        
        # Get last N context messages (before window start)
        context_messages = messages_before[-context_count:] if messages_before else []
        
        # Clean up internal timestamp field
        for m in context_messages:
            del m["_parsed_ts"]
        for m in messages_in_window:
            del m["_parsed_ts"]
        
        # Apply message limit to window messages
        if len(messages_in_window) > limit:
            messages_in_window = messages_in_window[-limit:]
        
        # Set default session info if not found
        if not session_info:
            session_info = {
                "key": path.stem,
                "kind": infer_kind_from_key(path.stem),
                "channel": "unknown",
                "displayName": ""
            }
        
        return {
            **session_info,
            "messages": messages_in_window,
            "context": context_messages
        }
        
    except Exception as e:
        # Log error but don't fail entire gather
        print(f"Warning: Failed to read {path}: {e}")
        return None


def infer_kind_from_key(key: str) -> str:
    """
    Infer session kind from session key.
    
    Args:
        key: Session key
        
    Returns:
        Inferred kind
    """
    key_lower = key.lower()
    
    if "subagent" in key_lower:
        return "other"  # Sub-agents show as "other"
    elif "cron" in key_lower:
        return "cron"
    elif "hook" in key_lower:
        return "hook"
    elif "node" in key_lower:
        return "node"
    elif "group" in key_lower or "channel" in key_lower:
        return "group"
    else:
        return "main"


def parse_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
    """
    Parse timestamp string to datetime.
    
    Args:
        timestamp_str: ISO format timestamp
        
    Returns:
        Datetime object or None if parsing fails
    """
    if not timestamp_str:
        return None
    
    try:
        # Try ISO format
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Convert to configured timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        else:
            dt = dt.astimezone(TZ)
        
        return dt
    except Exception:
        # Try timestamp as milliseconds
        try:
            dt = datetime.fromtimestamp(float(timestamp_str) / 1000, tz=TZ)
            return dt
        except Exception:
            return None


def call_gateway_api(method: str, params: dict) -> dict:
    """
    Call OpenClaw Gateway API.
    
    Args:
        method: API method (e.g., "sessions.list")
        params: Method parameters
        
    Returns:
        API response dict
        
    Raises:
        GatherError: If API call fails
    """
    url = f"{GATEWAY_URL}/api/rpc"
    headers = {
        "Authorization": f"Bearer {GATEWAY_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            raise GatherError(f"API error: {data['error']}")
        
        return data.get("result", {})
        
    except httpx.HTTPError as e:
        raise GatherError(f"HTTP error calling Gateway API: {e}")
    except Exception as e:
        raise GatherError(f"Failed to call Gateway API: {e}")
