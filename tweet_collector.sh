#!/bin/bash

set -e  # Exit immediately if any command fails.
set -a
source .venv/bin/activate
set +a

export PROJECT_PATH=${PROJECT_PATH:-$(pwd)}

## Source common bash utilities
source "${PROJECT_PATH}/utils/bash_utils.sh"

while true; do
    ## Create timestamped log file.
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="${PROJECT_PATH}/logs/tweet_collector_${TIMESTAMP}.log"
    
    echo "Tweet collection started at $(date)" | tee -a "$LOG_FILE" 2>/dev/null || true
    START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

    ## Exact 8 hour sleep.
    sleep_minutes=480
    total_seconds=$((sleep_minutes * 60))
    echo "Will sleep for ${sleep_minutes} minutes after collection..." | tee -a "$LOG_FILE"
    ## Run the tweet collector.
    python "executors/d0_collect_tweets.py" 2>&1 | tee -a "$LOG_FILE"
    
    ## Run tweet analysis.
    echo "Running tweet analysis..." | tee -a "$LOG_FILE"
    python "executors/d1_analyze_tweets.py" --start-time "$START_TIME" 2>&1 | tee -a "$LOG_FILE"
    
    ## Post analysis to X.com.
    echo "Posting analysis to X.com..." | tee -a "$LOG_FILE"
    python "executors/d2_post_analysis.py" 2>&1 | tee -a "$LOG_FILE"
    
    echo "Tweet collection completed at $(date)" | tee -a "$LOG_FILE"
    
    ## Use common utility for sleep with progress bar
    sleep_with_progress $total_seconds "Sleeping"
    
    echo "Waking up after ${sleep_minutes} minute sleep..." | tee -a "$LOG_FILE"
done 