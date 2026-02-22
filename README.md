# Captain's Logs — Memory Capture for OpenClaw

Continuous memory capture system that transforms periodic session activity into structured Captain's Log entries. Designed for [OpenClaw](https://github.com/openclaw/openclaw) AI agents.

Every 30 minutes, this system:
1. Gathers all session activity from the OpenClaw gateway
2. Counts tokens and batches if needed (>20K threshold)
3. Sends batches to an LLM (default: GPT-5.2) for summarization
4. Produces structured Captain's Log entries
5. Appends to daily memory files (`memory/YYYY-MM-DD.md`)

## Architecture

```
Session Activity → Gather → Tokenize → Batch → Summarize (LLM) → Consolidate → memory/YYYY-MM-DD.md
```

## Quick Start

```bash
git clone https://github.com/bill492/captains-log.git
cd captains-log

# Create virtual environment
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your OpenAI API key

# Run for current 30-minute window
./run.sh
```

## Usage

### Production (Live Mode)
```bash
# Run for current 30-minute window
./run.sh

# Custom window size
./run.sh --window 45

# Or use venv python directly
./venv/bin/python main.py
```

### Historical Mode (Backfill)
```bash
# Process a specific past window
./run.sh --end "2026-01-29T15:00:00" --mode historical

# Dry run (don't write files)
./run.sh --dry-run

# Bulk backfill a date range
./venv/bin/python scripts/migrate.py 2026-01-16 2026-01-30 --dry-run
```

## Configuration

All settings are configurable via environment variables. See `.env.example` for the full list.

Key settings:
- `OPENAI_API_KEY` — Required for LLM summarization
- `OPENCLAW_GATEWAY_URL` — Gateway API endpoint (default: `http://localhost:18789`)
- `CAPTAINS_LOG_TZ` — Timezone for log timestamps
- `CAPTAINS_LOG_MODEL` — LLM model to use (default: `gpt-5.2`)

## Scheduling

Add to cron for automatic capture:
```bash
crontab -e
# Run every 30 minutes:
*/30 * * * * cd /path/to/captains-log && ./run.sh >> logs/cron.log 2>&1
```

Or use OpenClaw's built-in cron:
```yaml
# In your OpenClaw config
crons:
  - name: "Captain's Logs"
    schedule: "*/30 * * * *"
    task: "Run captain's log capture"
    timeout: 300
```

## Project Structure

```
captains-log/
├── main.py              # Entry point
├── run.sh               # Convenience wrapper (uses venv)
├── state.json           # Tracks last run, errors (auto-generated)
├── src/
│   ├── config.py        # All settings (env-configurable)
│   ├── gather.py        # Fetch sessions (live/historical)
│   ├── tokenizer.py     # Token counting
│   ├── batcher.py       # Batch creation
│   ├── summarizer.py    # LLM API calls
│   ├── consolidator.py  # Merge & render markdown
│   ├── state.py         # State management
│   └── schemas.py       # Data models
├── prompts/
│   ├── captain_log_system.txt  # System prompt
│   └── captain_log_user.txt    # User prompt template
├── scripts/
│   └── migrate.py       # Historical backfill
├── tests/               # Test suite
├── caplogs/             # Daily run history (JSONL, auto-generated)
└── logs/                # Runtime logs (auto-generated)
```

## Output Format

Captain's Log entries are written to daily memory files:

```markdown
# Captain's Log — 2026-01-30

## 14:30 EST
Bill reviewed the PR feedback from Santhosh and pushed fixes for the auth flow...

**Remarks:** The session token refresh edge case needs a dedicated test.

---

## 15:00 EST
Quiet period. Heartbeat checks passed, no active sessions.
```

## How It Works

1. **Gather**: Queries the OpenClaw gateway API for all active sessions within the time window
2. **Tokenize**: Counts tokens using tiktoken (`o200k_base` encoding)
3. **Batch**: Groups messages into batches under the 30K token threshold
4. **Summarize**: Sends each batch to the LLM with system prompts for structured extraction
5. **Consolidate**: Merges summaries, deduplicates against previous entries, renders markdown
6. **Write**: Appends to `memory/YYYY-MM-DD.md` in your workspace

## State Management

The system tracks state in `state.json`:
- `last_successful_end_time`: Last successfully processed window
- `pending_errors`: Failed windows awaiting retry

After downtime, it automatically processes all missed windows in sequence.

## Testing

```bash
./venv/bin/python -m pytest tests/
```

## Requirements

- Python 3.11+
- OpenClaw instance with gateway API
- OpenAI API key (or compatible LLM provider)

## License

MIT
