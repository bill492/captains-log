# Captain's Logs - Quick Start Guide

## Prerequisites

✅ Already installed:
- Python 3.11.2
- Virtual environment created at `venv/`
- All dependencies installed

## Test the Installation

```bash
cd ~/clawd/captains-log

# Verify modules load
./venv/bin/python -c "import src.config; print('OK')"

# Run basic tests
./venv/bin/python tests/test_tokenizer.py

# View help
./run.sh --help
```

## First Test Run (Dry Run)

```bash
# Test on a historical window (won't write anything)
./run.sh --end "2026-01-30T14:00:00" --mode historical --dry-run
```

This will:
- Read transcripts from `~/.clawdbot/agents/main/sessions/`
- Show what would be processed
- Not write any files or call GPT-5.2

## Set Up OpenAI API Key

Before running for real, set your API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or add to `~/.bashrc`:
```bash
echo 'export OPENAI_API_KEY="sk-..."' >> ~/.bashrc
source ~/.bashrc
```

## Run Migration (Historical Backfill)

```bash
# Dry run first to see what would happen
./venv/bin/python migrate.py 2026-01-29 2026-01-30 --dry-run

# Run actual migration (costs money - calls GPT-5.2)
./venv/bin/python migrate.py 2026-01-29 2026-01-30
```

## Enable Production Cron

```bash
crontab -e

# Add this line:
*/30 * * * * cd ~/clawd/captains-log && ./run.sh >> logs/cron.log 2>&1
```

## Monitor

```bash
# Check cron output
tail -f ~/clawd/captains-log/logs/cron.log

# Check errors
tail -f ~/clawd/captains-log/logs/error.log

# Check run history
tail ~/clawd/captains-log/caplogs/2026-01-30.jsonl

# Check memory output
tail ~/clawd/memory/2026-01-30.md
```

## Troubleshooting

### "No such file or directory: sessions"
- Check that `~/.clawdbot/agents/main/sessions/` exists
- Historical mode requires JSONL transcripts to be present

### "API key not found"
- Set `OPENAI_API_KEY` environment variable

### "Gateway API timeout"
- Check that OpenClaw Gateway is running: `clawdbot gateway status`
- Verify token in `~/.clawdbot/clawdbot.json` matches config

### "Rate limited"
- Script will retry automatically with exponential backoff
- If persistent, wait 1-2 minutes and try again

## File Locations

```
~/clawd/captains-log/        # Project root
├── run.sh                   # Main entry point
├── state.json               # Tracks progress
├── caplogs/                 # Run history (JSONL)
│   └── YYYY-MM-DD.jsonl
├── logs/
│   ├── cron.log            # Cron output
│   └── error.log           # Errors
└── venv/                    # Python environment

~/clawd/memory/              # Output location
└── YYYY-MM-DD.md            # Captain's Log entries

~/.clawdbot/agents/main/sessions/  # Input (historical mode)
└── *.jsonl                  # Session transcripts
```

## Common Tasks

### Test on specific time period
```bash
./run.sh --end "2026-01-30T15:30:00" --mode historical --dry-run
```

### Run with custom window size
```bash
./run.sh --window 45  # 45-minute window
```

### Check state
```bash
cat state.json | jq .
```

### Clean up old caplogs (manual)
```bash
find caplogs/ -name "*.jsonl" -mtime +14 -delete
```

### Reset state (start fresh)
```bash
cp state.json state.json.backup
echo '{"last_successful_end_time": null, "pending_errors": []}' > state.json
```

## Success Indicators

After first successful run, you should see:

1. ✅ New entries in `~/clawd/memory/YYYY-MM-DD.md`
2. ✅ Run logged in `caplogs/YYYY-MM-DD.jsonl`
3. ✅ State updated in `state.json`
4. ✅ Exit code 0

## Getting Help

- Full documentation: `README.md`
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- Design docs: `~/clawd/md_refactor/captainsLogs*.md`

## Quick Smoke Test

```bash
# Full test without API calls
cd ~/clawd/captains-log

# 1. Verify imports
./venv/bin/python -c "from src.config import *; print('Config OK')"

# 2. Run tokenizer tests
./venv/bin/python tests/test_tokenizer.py

# 3. Show help
./run.sh --help

# 4. Dry run
./run.sh --dry-run

# If all 4 succeed: ✅ Ready to go!
```
