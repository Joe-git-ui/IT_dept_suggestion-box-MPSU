#!/bin/bash
# Gunicorn startup script for Render.com deployment

# Activate virtual environment if needed
# source /path/to/venv/bin/activate

# Run Gunicorn server
exec gunicorn app:app --bind 0.0.0.0:10000 --workers 3
