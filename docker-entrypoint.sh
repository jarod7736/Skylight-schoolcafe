#!/bin/bash
set -e

# Export environment variables to a file that cron can access
printenv | grep -v "no_proxy" > /etc/environment

# Run the script once on startup if RUN_ON_STARTUP is set
if [ "$RUN_ON_STARTUP" = "true" ]; then
    echo "Running initial menu sync..."
    cd /app && python3 src/getMenus.py
    echo "Initial sync complete."
fi

# Execute the command passed to the container
exec "$@"
