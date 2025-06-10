#!/bin/bash

set -e  ## Exit immediately if any command fails
set -a
source .venv/bin/activate
set +a

export PROJECT_PATH=${PROJECT_PATH:-$(pwd)}

## Source common bash utilities
source "${PROJECT_PATH}/utils/bash_utils.sh"

function sleep_until_target() {
    sleep_until_daily_time 18 30 "Daily Update"
}

function run_daily_update() {
    local temp_error_file="/tmp/daily_update_error_$TIMESTAMP.txt"
    
    echo ">> [Daily Update] Started at $(date)" | tee -a "$LOG_FILE"
    
    ## Run the Python script and capture output.
    python "${PROJECT_PATH}/executors/a1_daily_update.py" 2>&1 | tee -a "$LOG_FILE" "$temp_error_file"
    local exit_status=${PIPESTATUS[0]}
    
    if [ $exit_status -eq 2 ]; then
        ## If there are too few papers, log it as info and continue.
        echo ">> [Daily Update] Skipped - Too few papers (less than 4) in the last 24 hours" | tee -a "$LOG_FILE"
        rm -f "$temp_error_file"
        return 0
    elif [ $exit_status -ne 0 ]; then
        ## If the script failed, log the error.
        local error_msg=$(cat "$temp_error_file")
        rm -f "$temp_error_file"
        echo ">> [Daily Update] Failed at $(date) with error: $error_msg" | tee -a "$LOG_FILE"
        return 1
    fi
    
    ## Log successful run.
    rm -f "$temp_error_file"
    echo ">> [Daily Update] Completed at $(date)" | tee -a "$LOG_FILE"
    return 0
}

while true; do
    ## Create timestamped log file.
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="${PROJECT_PATH}/logs/daily_update_${TIMESTAMP}.log"
    
    echo "Daily Update process started at $(date)" | tee -a "$LOG_FILE"
    
    ## Wait until 7 PM PST/PDT.
    sleep_until_target
    
    ## Run the daily update.
    run_daily_update
    
    echo "Daily Update cycle completed at $(date)" | tee -a "$LOG_FILE"
    echo "Waiting for next cycle..."
done 