#!/usr/bin/env bash

# Launch RAG SDS Matrix UI with correct Python environment
# This ensures the virtual environment's Python is used

cd "$(dirname "$0")"
exec ./.venv/bin/python main.py
