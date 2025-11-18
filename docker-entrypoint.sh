#!/bin/bash
# TrashAlert Docker Entrypoint Script
# Handles database initialization and service startup

set -e

echo "================================================"
echo "TrashAlert Docker Container Starting"
echo "================================================"

# Initialize database if it doesn't exist
if [ ! -f "/app/data/trashalert.db" ]; then
    echo "Database not found. Initializing..."
    python init_db.py
    echo "Database initialized successfully."
else
    echo "Database already exists. Skipping initialization."
fi

# Execute the main command (passed as arguments to this script)
echo "Starting application: $@"
exec "$@"
