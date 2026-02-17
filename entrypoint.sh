#!/bin/sh

# Check if DOCKER-CRON is set
if [ -n "$DOCKER-CRON" ]; then
    # Run the Python script once
    python /swi/run.py

    # Add an alias for run-cron
    echo "alias run-cron='python /swi/run.py'" >> ~/.bashrc
    echo "Container is now waiting for commands. You can use 'run-cron' to re-run the script."
    exec /bin/sh
else
    # Default behavior: just run the Python script
    exec python /swi/run.py
fi
