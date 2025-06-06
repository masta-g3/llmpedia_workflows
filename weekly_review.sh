#!/bin/bash

set -e  ## Exit immediately if any command fails
set -a
source .venv/bin/activate
set +a

PROJECT_PATH=${PROJECT_PATH:-.}

function show_progress() {
    local elapsed=$1
    local total=$2
    local pct=$((elapsed * 100 / total))
    local filled=$((pct / 2))
    local unfilled=$((50 - filled))
    
    printf "\r["
    printf "%${filled}s" '' | tr ' ' '#'
    printf "%${unfilled}s" '' | tr ' ' '-'
    printf "] %d%% (%dm %ds/%dm)" $pct $((elapsed / 60)) $((elapsed % 60)) $((total / 60))
}

function sleep_until_wednesday() {
    ## Get current time in seconds since epoch.
    current_time=$(date +%s)
    
    ## Get current day of week (1=Monday, ..., 3=Wednesday, ..., 7=Sunday)
    current_day=$(date +%u)
    
    ## Calculate target time (3:00 PM PST/PDT) for next Wednesday.
    local target_hour=15 # 3 PM
    local target_day=3   # Wednesday
    
    if [ "$current_day" -eq "$target_day" ]; then
        ## If today is Wednesday, calculate target for 3 PM today.
        target_time_today=$(TZ=PST8PDT date -v${target_hour}H -v00M -v00S +%s)
        if [ "$current_time" -lt "$target_time_today" ]; then
            ## If it's before 3 PM today, set target to today.
            target_time=$target_time_today
        else
            ## If it's past 3 PM today, set target to next Wednesday.
            target_time=$(TZ=PST8PDT date -v+7d -v${target_hour}H -v00M -v00S +%s)
        fi
    else
        ## If today is not Wednesday, calculate days until next Wednesday.
        if [ "$current_day" -lt "$target_day" ]; then
            days_until_target=$(($target_day - $current_day))
        else # current_day > target_day (Thu, Fri, Sat, Sun)
            days_until_target=$(($target_day - $current_day + 7))
        fi
        
        ## Set target to next Wednesday at 3:00 PM.
        target_time=$(TZ=PST8PDT date -v+${days_until_target}d -v${target_hour}H -v00M -v00S +%s)
    fi
    
    ## Calculate seconds until target.
    seconds_to_wait=$((target_time - current_time))
    
    ## Ensure wait time is non-negative (edge case if clock changes)
    if [ "$seconds_to_wait" -lt 0 ]; then
        seconds_to_wait=0
    fi
    
    echo "Waiting until next Wednesday at 3:00 PM PST/PDT..." | tee -a "$LOG_FILE"
    echo "Current time: $(date)" | tee -a "$LOG_FILE"
    echo "Target time: $(date -r $target_time)" | tee -a "$LOG_FILE"
    
    ## Show progress bar while waiting.
    for ((i=0; i<=$seconds_to_wait; i++)); do
        show_progress $i $seconds_to_wait
        sleep 1
    done
    printf "\n"
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