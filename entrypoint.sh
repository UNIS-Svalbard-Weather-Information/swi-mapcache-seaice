#!/bin/sh

# Function to run the Python script, ensuring only one instance runs at a time
run_script() {
    if ! pidof -x "python" >/dev/null; then
        python /swi/run.py
    else
        echo "Another instance of run.py is already running. Skipping."
    fi
}

# Check if DOCKER-CRON is set
if [ -n "$DOCKER-CRON" ]; then
    # Run the Python script once (with instance check)
    run_script

    # Add an alias for run-cron
    echo "alias run-cron='run_script'" >> ~/.bashrc
    echo "Container is now waiting for commands. You can use 'run-cron' to re-run the script."

    # Keep the container running, but respect termination signals
    exec sh -c "sleep infinity & wait"
else
    # Default behavior: just run the Python script
    exec python /swi/run.py
fi
