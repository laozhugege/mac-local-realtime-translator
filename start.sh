#!/bin/bash
# Realtime Translator - Quick Launch Script
cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt -q

python main_agent.py
