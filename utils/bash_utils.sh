#!/bin/bash

## Common bash utilities for llmpedia workflows

## Show a progress bar for waiting/sleeping operations
## Args: $1 = elapsed seconds, $2 = total seconds
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

## Sleep with progress bar for a specified number of seconds
## Args: $1 = total seconds to sleep, $2 = description (optional)
function sleep_with_progress() {
    local total_seconds=$1
    local description=${2:-"Sleeping"}
    
    echo "$description for $((total_seconds / 60)) minutes..."
    
    for ((i=0; i<=$total_seconds; i++)); do
        show_progress $i $total_seconds
        sleep 1
    done
    printf "\n"
}

## Calculate target time for a specific hour/minute today or tomorrow if already passed
## Args: $1 = target hour (24h format), $2 = target minute, $3 = timezone (default: PST8PDT)
function calculate_daily_target() {
    local target_hour=$1
    local target_minute=$2
    local timezone=${3:-"PST8PDT"}
    
    local current_time=$(date +%s)
    local target_time=$(TZ=$timezone date -v${target_hour}H -v${target_minute}M -v00S +%s)
    
    ## If current time is past target time, set target to tomorrow
    if [ $current_time -gt $target_time ]; then
        target_time=$(TZ=$timezone date -v+1d -v${target_hour}H -v${target_minute}M -v00S +%s)
    fi
    
    echo $target_time
}

## Sleep until a specific time (hour:minute) daily
## Args: $1 = target hour (24h format), $2 = target minute, $3 = description, $4 = timezone (optional)
function sleep_until_daily_time() {
    local target_hour=$1
    local target_minute=$2
    local description=$3
    local timezone=${4:-"PST8PDT"}
    
    local current_time=$(date +%s)
    local target_time=$(calculate_daily_target $target_hour $target_minute $timezone)
    local seconds_to_wait=$((target_time - current_time))
    
    echo "Waiting until ${target_hour}:$(printf "%02d" $target_minute) $timezone for $description..." | tee -a "$LOG_FILE"
    echo "Current time: $(date)" | tee -a "$LOG_FILE"
    echo "Target time: $(date -r $target_time)" | tee -a "$LOG_FILE"
    
    for ((i=0; i<=$seconds_to_wait; i++)); do
        show_progress $i $seconds_to_wait
        sleep 1
    done
    printf "\n"
}

## Calculate target time for next occurrence of a specific weekday and time
## Args: $1 = target weekday (1=Monday, ..., 7=Sunday), $2 = target hour, $3 = target minute, $4 = timezone (optional)
function calculate_weekly_target() {
    local target_day=$1
    local target_hour=$2
    local target_minute=$3
    local timezone=${4:-"PST8PDT"}
    
    local current_time=$(date +%s)
    local current_day=$(date +%u)
    
    if [ "$current_day" -eq "$target_day" ]; then
        ## If today is the target day, calculate target for today
        local target_time_today=$(TZ=$timezone date -v${target_hour}H -v${target_minute}M -v00S +%s)
        if [ "$current_time" -lt "$target_time_today" ]; then
            echo $target_time_today
        else
            ## If it's past the target time today, set target to next week
            echo $(TZ=$timezone date -v+7d -v${target_hour}H -v${target_minute}M -v00S +%s)
        fi
    else
        ## Calculate days until target weekday
        if [ "$current_day" -lt "$target_day" ]; then
            local days_until_target=$(($target_day - $current_day))
        else
            local days_until_target=$(($target_day - $current_day + 7))
        fi
        
        echo $(TZ=$timezone date -v+${days_until_target}d -v${target_hour}H -v${target_minute}M -v00S +%s)
    fi
}

## Sleep until a specific weekday and time
## Args: $1 = target weekday (1=Monday, ..., 7=Sunday), $2 = target hour, $3 = target minute, $4 = description, $5 = timezone (optional)
function sleep_until_weekly_time() {
    local target_day=$1
    local target_hour=$2
    local target_minute=$3
    local description=$4
    local timezone=${5:-"PST8PDT"}
    
    local weekdays=("" "Monday" "Tuesday" "Wednesday" "Thursday" "Friday" "Saturday" "Sunday")
    local weekday_name=${weekdays[$target_day]}
    
    local current_time=$(date +%s)
    local target_time=$(calculate_weekly_target $target_day $target_hour $target_minute $timezone)
    local seconds_to_wait=$((target_time - current_time))
    
    ## Ensure wait time is non-negative
    if [ "$seconds_to_wait" -lt 0 ]; then
        seconds_to_wait=0
    fi
    
    echo "Waiting until next $weekday_name at ${target_hour}:$(printf "%02d" $target_minute) $timezone for $description..." | tee -a "$LOG_FILE"
    echo "Current time: $(date)" | tee -a "$LOG_FILE"
    echo "Target time: $(date -r $target_time)" | tee -a "$LOG_FILE"
    
    for ((i=0; i<=$seconds_to_wait; i++)); do
        show_progress $i $seconds_to_wait
        sleep 1
    done
    printf "\n"
} 