#!/bin/bash

# Reddit Collection and Analysis Workflow
# Runs daily at 9:00 AM PST, similar to daily_update.sh pattern

set -e  ## Exit immediately if any command fails
set -a
source .venv/bin/activate 2>/dev/null || true
set +a

export PROJECT_PATH=${PROJECT_PATH:-$(pwd)}

## Source common bash utilities
source "${PROJECT_PATH}/utils/bash_utils.sh"

function sleep_until_target() {
    sleep_until_daily_time 9 0 "Reddit collection"
}

function run_reddit_workflow() {
    local temp_error_file="/tmp/reddit_workflow_error_$TIMESTAMP.txt"
    
    echo ">> [Reddit Workflow] Started at $(date)" | tee -a "$LOG_FILE"
    
    # Capture start time before collection (like tweet_collector.sh)
    START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
    echo "Reddit workflow started at: $START_TIME" | tee -a "$LOG_FILE"
    
    # Calculate 24-hour lookback period for collection (aligned collection and analysis)
    # Uses macOS/BSD date format first, falls back to GNU date format
    COLLECTION_START_TIME=$(date -v-24H +"%Y-%m-%d %H:%M:%S" 2>/dev/null || date -d "24 hours ago" +"%Y-%m-%d %H:%M:%S")
    echo "Collection window: $COLLECTION_START_TIME to now (exactly 24 hours)" | tee -a "$LOG_FILE"

    # Step 1: Collect Reddit posts and comments (100 posts per subreddit)
    echo "Step 1: Collecting Reddit posts and comments..." | tee -a "$LOG_FILE"
    python "executors/e0_collect_reddit.py" --start-date "$COLLECTION_START_TIME" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo ">> [Reddit Workflow] Collection failed at $(date)" | tee -a "$LOG_FILE"
        local error_msg=$(cat "$temp_error_file")
        rm -f "$temp_error_file"
        echo "Error: $error_msg" | tee -a "$LOG_FILE"
        return 1
    fi

    # Step 2: Analyze Reddit content patterns (individual subreddits)
    echo "Step 2: Analyzing individual subreddit patterns..." | tee -a "$LOG_FILE"
    python "executors/e1_analyze_reddit.py" --priority 1 --start-time "$COLLECTION_START_TIME" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo ">> [Reddit Workflow] Individual analysis failed at $(date)" | tee -a "$LOG_FILE"
        local error_msg=$(cat "$temp_error_file")
        rm -f "$temp_error_file"
        echo "Error: $error_msg" | tee -a "$LOG_FILE"
        return 1
    fi

    # Step 2.5: Cross-subreddit analysis (ecosystem-wide insights)
    echo "Step 2.5: Performing cross-subreddit analysis..." | tee -a "$LOG_FILE"
    python "executors/e1_analyze_reddit.py" --priority 1 --cross-subreddit --start-time "$COLLECTION_START_TIME" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo ">> [Reddit Workflow] Cross-subreddit analysis failed at $(date)" | tee -a "$LOG_FILE"
        local error_msg=$(cat "$temp_error_file")
        rm -f "$temp_error_file"
        echo "Error: $error_msg" | tee -a "$LOG_FILE"
        return 1
    fi

    # Step 3: Post Reddit cross-analysis to X.com (prioritize cross-subreddit analysis)
    echo "Step 3: Posting Reddit cross-analysis to X.com..." | tee -a "$LOG_FILE"
    python "executors/e2_post_reddit_analysis.py" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        echo ">> [Reddit Workflow] Analysis posting failed at $(date)" | tee -a "$LOG_FILE"
        local error_msg=$(cat "$temp_error_file")
        rm -f "$temp_error_file"
        echo "Error: $error_msg" | tee -a "$LOG_FILE"
        return 1
    fi

    ## Log successful run.
    rm -f "$temp_error_file"
    echo ">> [Reddit Workflow] Completed successfully at $(date)" | tee -a "$LOG_FILE"
    return 0
}

while true; do
    ## Create timestamped log file.
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="${PROJECT_PATH}/logs/reddit_collector_${TIMESTAMP}.log"
    
    echo "Reddit collection process started at $(date)" | tee -a "$LOG_FILE"
    
    ## Wait until 9:00 AM PST.
    sleep_until_target
    
    ## Run the Reddit workflow.
    run_reddit_workflow
    
    echo "Reddit collection cycle completed at $(date)" | tee -a "$LOG_FILE"
    echo "Waiting for next cycle (next day at 9:00 AM PST)..." | tee -a "$LOG_FILE"
done 