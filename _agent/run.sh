#!/usr/bin/env bash
# Daily entry point for the interview-prep monitoring agent.
set -e
cd "$(dirname "$0")"
python3 -m pip install --user --quiet anthropic 2>/dev/null || true
exec python3 orchestrator.py "$@"
