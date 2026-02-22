#!/usr/bin/env python3
"""
Migration script to backfill historical Captain's Logs.

Usage:
    python scripts/migrate.py START_DATE END_DATE [--dry-run]
    
Example:
    python scripts/migrate.py 2026-01-16 2026-01-30
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Load API key from secrets before importing anything else
secrets_path = Path.home() / ".clawdbot" / "secrets" / "anthropic.env"
if secrets_path.exists():
    with open(secrets_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import TZ, WINDOW_DELAY
from main import process_window
import time as time_module


def migrate_date_range(
    start_date: str, 
    end_date: str,
    dry_run: bool = False
):
    """
    Backfill Captain's Logs for a date range.
    
    Args:
        start_date: "YYYY-MM-DD" 
        end_date: "YYYY-MM-DD"
        dry_run: If True, don't write files
    """
    # Parse dates
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=TZ)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=TZ)
        end = end.replace(hour=23, minute=59)  # End of day
    except ValueError as e:
        print(f"Error: Invalid date format: {e}")
        print("Use YYYY-MM-DD format (e.g., 2026-01-30)")
        return 1
    
    if start > end:
        print("Error: Start date must be before end date")
        return 1
    
    # Calculate window times (every 30 minutes)
    current = start + timedelta(minutes=30)
    total_windows = 0
    successful = 0
    skipped = 0
    failed = 0
    
    print(f"\nMigrating Captain's Logs from {start_date} to {end_date}")
    if dry_run:
        print("DRY RUN MODE - No files will be written\n")
    print("="*60)
    
    while current <= end:
        total_windows += 1
        print(f"\n[{total_windows}] Processing: {current.isoformat()}")
        
        try:
            result = process_window(
                end_time=current,
                window_minutes=30,
                mode="historical",
                dry_run=dry_run
            )
            
            if result["status"] == "ok":
                successful += 1
                entries = result.get("entries", 0)
                print(f"  [OK] Success: {entries} entries")
            elif result["status"] == "skip":
                skipped += 1
                print(f"  [--] Skipped: {result.get('reason', 'no activity')}")
            else:
                failed += 1
                error = result.get("error", "Unknown error")
                print(f"  [!!] Error: {error}")
                
        except KeyboardInterrupt:
            print("\n\nMigration interrupted by user")
            break
        except Exception as e:
            failed += 1
            print(f"  [!!] Unexpected error: {e}")
        
        # Rate limit: delay between windows
        if WINDOW_DELAY > 0:
            time_module.sleep(WINDOW_DELAY)
        
        current += timedelta(minutes=30)
    
    # Summary
    print("\n" + "="*60)
    print("Migration Summary")
    print("="*60)
    print(f"Total windows:  {total_windows}")
    print(f"Successful:     {successful}")
    print(f"Skipped:        {skipped}")
    print(f"Failed:         {failed}")
    
    if dry_run:
        print("\nDRY RUN - No files were written")
    
    return 0 if failed == 0 else 1


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill historical Captain's Logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Migrate two weeks of data
    python scripts/migrate.py 2026-01-16 2026-01-30
    
    # Dry run to see what would happen
    python scripts/migrate.py 2026-01-16 2026-01-30 --dry-run
    
    # Migrate a single day
    python scripts/migrate.py 2026-01-30 2026-01-30
        """
    )
    parser.add_argument(
        "start_date",
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "end_date",
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write files, just show what would happen"
    )
    
    args = parser.parse_args()
    
    return migrate_date_range(args.start_date, args.end_date, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
