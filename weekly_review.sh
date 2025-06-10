#!/bin/bash

set -e  ## Exit immediately if any command fails
set -a
source .venv/bin/activate
set +a

PROJECT_PATH=${PROJECT_PATH:-.}

## Source common bash utilities
source "${PROJECT_PATH}/utils/bash_utils.sh"

function sleep_until_wednesday() {
    sleep_until_weekly_time 3 15 0 "Weekly Review"  ## Wednesday (3), 3:00 PM (15:00)
}

function get_previous_monday_date() {
    ## Get date for Monday of the previous week (7 days ago)
    TZ=PST8PDT date -v-7d -v-mon +%Y-%m-%d
}

function run_weekly_review() {
    local temp_error_file="/tmp/weekly_review_error_$TIMESTAMP.txt"
    local prev_monday=$(get_previous_monday_date)
    
    echo ">> [Weekly Review] Started at $(date)" | tee -a "$LOG_FILE"
    echo ">> [Weekly Review] Using date: $prev_monday" | tee -a "$LOG_FILE"
    
    ## Run the Python script and capture output.
    python "${PROJECT_PATH}/executors/b1_weekly_review.py" "$prev_monday" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    local exit_status=${PIPESTATUS[0]}
    
    if [ $exit_status -ne 0 ]; then
        ## If the script failed, log the error.
        local error_msg=$(cat "$temp_error_file")
        python -c "from utils.db.logging_db import log_workflow_run; log_workflow_run('Weekly Review', 'executors/b1_weekly_review.py', 'error', '''$error_msg''')"
        rm -f "$temp_error_file"
        echo ">> [Weekly Review] Failed at $(date)" | tee -a "$LOG_FILE"
        return 1
    fi
    
    ## Log successful run of b1_weekly_review.py.
    python -c "from utils.db.logging_db import log_workflow_run; log_workflow_run('Weekly Review', 'executors/b1_weekly_review.py', 'success')"
    rm -f "$temp_error_file" # Remove temp file now, it's not needed for the next step
    echo ">> [Weekly Review - b1] Completed at $(date)" | tee -a "$LOG_FILE"

    ## Run the tweet script if the previous step succeeded.
    echo ">> [Weekly Review Tweet] Started at $(date)" | tee -a "$LOG_FILE"
    python "${PROJECT_PATH}/executors/a3_weekly_review_tweet.py" "$prev_monday" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    local tweet_exit_status=${PIPESTATUS[0]}

    if [ $tweet_exit_status -ne 0 ]; then
        ## If the tweet script failed, log the error.
        local tweet_error_msg=$(cat "$temp_error_file")
        python -c "from utils.db.logging_db import log_workflow_run; log_workflow_run('Weekly Review Tweet', 'executors/a3_weekly_review_tweet.py', 'error', '''$tweet_error_msg''')"
        rm -f "$temp_error_file"
        echo ">> [Weekly Review Tweet] Failed at $(date)" | tee -a "$LOG_FILE"
        ## Note: We return 0 here because the main review completed, only the tweet failed.
        ## Consider if a tweet failure should cause the entire function to return 1.
        return 0 
    fi
    
    ## Log successful tweet run.
    python -c "from utils.db.logging_db import log_workflow_run; log_workflow_run('Weekly Review Tweet', 'executors/a3_weekly_review_tweet.py', 'success')"
    rm -f "$temp_error_file"
    echo ">> [Weekly Review Tweet] Completed at $(date)" | tee -a "$LOG_FILE"
    
    return 0
}

while true; do
    ## Create timestamped log file.
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="${PROJECT_PATH}/logs/weekly_review_${TIMESTAMP}.log"
    
    echo "Weekly Review process started at $(date)" | tee -a "$LOG_FILE"
     
    ## Wait until next Wednesday at 3:00 PM PST/PDT.
    sleep_until_wednesday
    
    ## Run the weekly review.
    run_weekly_review
    
    echo "Weekly Review cycle completed at $(date)" | tee -a "$LOG_FILE"
    echo "Waiting for next cycle..."
done 