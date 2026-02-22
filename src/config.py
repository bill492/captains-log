"""Configuration for Captain's Logs."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Timezone
TZ = ZoneInfo(os.environ.get("CAPTAINS_LOG_TZ", "America/New_York"))

# Paths
BASE_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = Path(os.environ.get("OPENCLAW_WORKSPACE", Path.home() / "clawd"))
MEMORY_DIR = Path(os.environ.get("CAPTAINS_LOG_MEMORY_DIR", WORKSPACE_DIR / "memory"))
CAPLOGS_DIR = BASE_DIR / "caplogs"
LOGS_DIR = BASE_DIR / "logs"
PROMPTS_DIR = BASE_DIR / "prompts"
STATE_FILE = BASE_DIR / "state.json"
SESSIONS_DIR = Path(os.environ.get(
    "OPENCLAW_SESSIONS_DIR",
    Path.home() / ".openclaw" / "agents" / "main" / "sessions"
))

# Ensure directories exist
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
CAPLOGS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

# OpenClaw Gateway API
GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:18789")
GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

# Session gathering
ACTIVE_MINUTES = int(os.environ.get("CAPTAINS_LOG_WINDOW_MINUTES", "30"))
MESSAGE_LIMIT = 100
SESSION_KINDS = ["main", "group", "other"]  # Include sub-agents

# Token thresholds
MAX_TOKENS_PER_BATCH = 30000
TOKEN_MODEL = "o200k_base"  # tiktoken encoding for GPT-5.x

# Model configuration
MODEL = os.environ.get("CAPTAINS_LOG_MODEL", "gpt-5.2")
PROVIDER = os.environ.get("CAPTAINS_LOG_PROVIDER", "openai")
REASONING_EFFORT = os.environ.get("CAPTAINS_LOG_REASONING", "medium")
MAX_OUTPUT_TOKENS = 4096

# Context
INCLUDE_PREVIOUS_SUMMARIES = 2  # Last N summaries for deduplication
CONTEXT_MESSAGES = 4  # Messages before window to include for context

# API retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
RETRY_BACKOFF = 2  # exponential backoff multiplier
