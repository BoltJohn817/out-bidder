#!/bin/bash
# Azure Web App startup script

# Activate virtual environment if it exists (for local testing)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies if needed (Azure usually handles this, but just in case)
pip install -r requirements.txt --quiet

# Start Gunicorn with the configuration file
exec gunicorn --config gunicorn_config.py app:application

