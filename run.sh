#!/bin/bash
# Wrapper script to run Captain's Logs with venv

cd "$(dirname "$0")"

# Force UTF-8 encoding for Python (handles unicode in transcripts)
export PYTHONIOENCODING=utf-8
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Load OpenAI API key (dotenv handles .env, but export for safety)
if [[ -f .env ]]; then
    source .env
    export OPENAI_API_KEY
fi

exec ./venv/bin/python main.py "$@"
