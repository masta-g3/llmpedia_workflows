#!/bin/bash

set -e  # Exit immediately if any command fails
set -a
source .venv/bin/activate 2>/dev/null || true
set +a

# Set the project path
export PROJECT_PATH=${PROJECT_PATH:-$(pwd)}

# Create log directory if it doesn't exist
mkdir -p "${PROJECT_PATH}/logs"

# Create timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${PROJECT_PATH}/logs/tweet_sender_${TIMESTAMP}.log"

echo "Tweet sender started at $(date)" | tee -a "$LOG_FILE"

# Run the tweet sender in continuous mode to check for approved tweets
echo "Starting tweet sender in continuous mode..." | tee -a "$LOG_FILE"

# Run with error handling
python "${PROJECT_PATH}/executors/a3_tweet_sender.py" --continuous --interval 300 2>&1 | tee -a "$LOG_FILE"

# If we get here, the sender has stopped
echo "Tweet sender stopped at $(date)" | tee -a "$LOG_FILE"

# Exit with the status of the Python script
exit ${PIPESTATUS[0]} 