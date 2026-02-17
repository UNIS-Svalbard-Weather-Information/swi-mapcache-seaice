#!/bin/sh

# Ensure only one instance of /swi/run.py runs at a time
if ! pidof -x "python" >/dev/null; then
    python /swi/run.py
else
    echo "Another instance of run.py is already running. Skipping."
fi
