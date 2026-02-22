#!/usr/bin/env python3
"""
Captain's Log - Memory capture system.

Gathers session activity, summarizes with GPT-5.2,
and produces structured Captain's Log entries.
"""

import argparse
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Force UTF-8 encoding for transcripts with unicode (curly quotes, emoji, etc.)
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import TZ, LOGS_DIR
from src.gather import gather_sessions, GatherError
from src.batcher import create_batches, get_batch_info
from src.summarizer import summarize_batch, SummarizerError
from src.consolidator import (
    merge_outputs, render_markdown, append_to_daily_file,
    create_run_entry
)
from src.state import (
    load_state, save_state, get_windows_to_process,
    update_state_success, update_state_error,
    get_previous_summaries, append_to_caplog
)


def process_window(
    end_time: datetime,
    window_minutes: int = 30,
    mode: str = "live",
    dry_run: bool = False
) -> dict:
    """
    Process a single time window.
    
    Args:
        end_time: End of window
        window_minutes: Window size in minutes
        mode: "live" or "historical"
        dry_run: If True, don't write files
        
    Returns:
        Result dict with status and metrics
    """
    start_ms = datetime.now().timestamp() * 1000
    date = end_time.strftime("%Y-%m-%d")
    
    try:
        # 1. Gather sessions
        print(f"Gathering sessions for window ending {end_time.isoformat()}...")
        sessions = gather_sessions(
            end_time=end_time,
            window_minutes=window_minutes,
            mode=mode
        )
        
        # Check if any activity
        if not sessions:
            duration_ms = int(datetime.now().timestamp() * 1000 - start_ms)
            print("No activity in this window. Skipping.")
            
            result = {
                "status": "skip",
                "reason": "no_activity",
                "duration_ms": duration_ms
            }
            
            if not dry_run:
                run_entry = create_run_entry(
                    timestamp=end_time,
                    status="skip",
                    reason="no_activity",
                    duration_ms=duration_ms
                )
                append_to_caplog(run_entry, date)
            
            return result
        
        print(f"Found {len(sessions)} active sessions")
        
        # 2. Create batches
        batches = create_batches(sessions)
        batch_info = get_batch_info(batches)
        
        print(f"Created {batch_info['num_batches']} batches "
              f"({batch_info['total_tokens']} total tokens)")
        
        # 3. Get previous summaries for context
        previous_summaries = get_previous_summaries(n=2)
        
        # 4. Summarize each batch
        outputs = []
        total_tokens_in = 0
        total_tokens_out = 0
        
        for i, batch in enumerate(batches):
            print(f"Summarizing batch {i + 1}/{len(batches)}...")
            
            try:
                output = summarize_batch(batch, previous_summaries)
                outputs.append(output)
                
                # Track tokens (estimate for now)
                total_tokens_in += batch_info['batch_tokens'][i]
                total_tokens_out += len(output.get('summary', '')) // 4
                
            except SummarizerError as e:
                print(f"Warning: Failed to summarize batch {i + 1}: {e}")
                # Continue with other batches
                continue
        
        if not outputs:
            raise SummarizerError("All batches failed to summarize")
        
        # 5. Consolidate outputs
        all_entries = merge_outputs(outputs)
        print(f"Generated {len(all_entries)} log entries")
        
        # 6. Render markdown
        markdown = render_markdown(all_entries, date)
        
        # 7. Write to daily file (unless dry-run)
        if not dry_run:
            append_to_daily_file(markdown, date)
            print(f"Appended to memory/{date}.md")
            
            # Log run to caplog
            summary = outputs[0].get('summary', '') if outputs else ''
            run_entry = create_run_entry(
                timestamp=end_time,
                status="ok",
                sessions=len(sessions),
                batches=len(batches),
                entries=len(all_entries),
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                duration_ms=int(datetime.now().timestamp() * 1000 - start_ms),
                summary=summary
            )
            append_to_caplog(run_entry, date)
        else:
            print("\n--- DRY RUN OUTPUT ---")
            print(markdown)
            print("--- END DRY RUN ---\n")
        
        return {
            "status": "ok",
            "sessions": len(sessions),
            "batches": len(batches),
            "entries": len(all_entries),
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "duration_ms": int(datetime.now().timestamp() * 1000 - start_ms)
        }
        
    except (GatherError, SummarizerError) as e:
        duration_ms = int(datetime.now().timestamp() * 1000 - start_ms)
        error_msg = str(e)
        
        print(f"Error processing window: {error_msg}")
        
        # Log error
        if not dry_run:
            log_error(end_time, error_msg)
            
            run_entry = create_run_entry(
                timestamp=end_time,
                status="error",
                error=error_msg,
                duration_ms=duration_ms
            )
            append_to_caplog(run_entry, date)
        
        return {
            "status": "error",
            "error": error_msg,
            "duration_ms": duration_ms
        }
    
    except Exception as e:
        duration_ms = int(datetime.now().timestamp() * 1000 - start_ms)
        error_msg = f"Unexpected error: {e}\n{traceback.format_exc()}"
        
        print(error_msg)
        
        # Log error
        if not dry_run:
            log_error(end_time, error_msg)
            
            run_entry = create_run_entry(
                timestamp=end_time,
                status="error",
                error=str(e),
                duration_ms=duration_ms
            )
            append_to_caplog(run_entry, date)
        
        return {
            "status": "error",
            "error": str(e),
            "duration_ms": duration_ms
        }


def log_error(window_end: datetime, error: str) -> None:
    """
    Log error to error.log.
    
    Args:
        window_end: Window end time
        error: Error message
    """
    error_log = LOGS_DIR / "error.log"
    
    timestamp = datetime.now(TZ).isoformat()
    log_entry = f"\n[{timestamp}] Window: {window_end.isoformat()}\n{error}\n"
    
    with open(error_log, 'a') as f:
        f.write(log_entry)


def run_captain_log(
    end_time: datetime = None,
    window_minutes: int = 30,
    mode: str = "live",
    dry_run: bool = False
) -> dict:
    """
    Main entry point with catch-up processing.
    
    Args:
        end_time: End time for window (defaults to now)
        window_minutes: Window size in minutes
        mode: "live" or "historical"
        dry_run: If True, don't write files or update state
        
    Returns:
        Final result dict
    """
    # Load state
    state = load_state()
    
    # Determine windows to process
    if end_time is not None or mode == "historical":
        # Single window mode (for historical or explicit end time)
        if end_time is None:
            end_time = datetime.now(TZ)
        windows = [end_time]
    else:
        # Live mode with catch-up
        windows = get_windows_to_process(state, interval_minutes=window_minutes)
    
    print(f"Processing {len(windows)} window(s)...")
    
    last_result = None
    
    for window_end in windows:
        print(f"\n{'='*60}")
        print(f"Window: {window_end.isoformat()}")
        print('='*60)
        
        result = process_window(window_end, window_minutes, mode, dry_run)
        last_result = result
        
        # Update state after each window (unless dry-run)
        if not dry_run:
            if result["status"] == "ok" or result["status"] == "skip":
                state = update_state_success(state, window_end)
                save_state(state)
            else:
                state = update_state_error(state, window_end, result.get("error", "Unknown error"))
                save_state(state)
                # Stop on first error
                print("Stopping due to error. Will retry on next run.")
                break
    
    return last_result or {"status": "error", "error": "No windows processed"}


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Captain's Log - Memory capture system"
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End time (ISO 8601), defaults to now"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=30,
        help="Window size in minutes (default: 30)"
    )
    parser.add_argument(
        "--mode",
        choices=["live", "historical"],
        default="historical",
        help="live=API, historical=transcripts (default: historical)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write output files or update state"
    )
    
    args = parser.parse_args()
    
    # Parse end time if provided
    end_time = None
    if args.end:
        try:
            end_time = datetime.fromisoformat(args.end)
            
            # Ensure timezone
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=TZ)
            else:
                end_time = end_time.astimezone(TZ)
        except Exception as e:
            print(f"Error: Invalid end time: {e}")
            return 1
    
    # Run
    result = run_captain_log(
        end_time=end_time,
        window_minutes=args.window,
        mode=args.mode,
        dry_run=args.dry_run
    )
    
    # Return appropriate exit code
    if result["status"] in ("ok", "skip"):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
