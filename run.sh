#!/bin/bash
# Simple run script for development

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the application
python3 main.py "$@"
