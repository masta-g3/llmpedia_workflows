# Changelog

## 2025-02-08

- Added a daily update executor that tweets the number of new papers added in the last 24 hours.
- Added daily_update.sh script to automate running of daily updates at 7 PM PST/PDT with progress tracking and logging
- Modified daily update to skip when fewer than 4 papers are found in 24 hours
- Added new tweet_replies table to store responses to tweets with metadata

## 2025-02-17

### Database Operations Refactoring
- Modularized database operations into specialized modules:
  - `db_utils.py`: Core database utilities and helper functions
  - `paper_db.py`: Paper-related database operations
  - `tweet_db.py`: Tweet-related database operations
  - `embedding_db.py`: Embedding-related database operations
  - `logging_db.py`: Logging-related database operations
- Added `simple_select_query` helper function to standardize simple SELECT queries
- Improved error handling and logging across all database operations
- Optimized batch operations for embedding storage
- Maintained backward compatibility through re-exports in `db.py`
- Cleaned up duplicate files:
  - Removed `utils/paper_db.py` in favor of `utils/db/paper_db.py`
  - Removed `utils/tweet_db.py` in favor of `utils/db/tweet_db.py`
- Updated tests to use mocks for write operations while keeping read operations on real database

## 2025-02-19

### Tweet Generation System Refactoring
- Implemented new configuration-driven tweet generation system:
  - Added Pydantic models for tweet configuration
  - Created YAML-based configuration system
  - Modularized content and image generation functions
  - Added comprehensive thread verification system
- Enhanced tweet sending functionality:
  - Improved error handling and logging
  - Added pre-send verification
  - Made UI element detection more robust
  - Better image upload handling
- Moved tweet configurations to `config/tweet_types.yaml`

## 2025-02-20

### Tweet System Integration
- Unified tweet sending logic in `utils/tweet.py`:
  - Moved data models and verification functions from `z2_generate_tweet.py`
  - Created a flexible `TweetThread` model that works for both paper tweets and other types
  - Added `create_simple_tweet()` factory method for easy creation of simple tweets
- Enhanced `send_tweet2()` to support both complex and simple tweets:
  - Added type checking to handle different input formats
  - Maintained backward compatibility with old parameters
  - Improved verification for all tweet types
- Updated Daily Update script to use the new system:
  - Created `create_daily_update_tweet()` function
  - Added metadata tracking for statistics
  - Integrated with verification system
- Improved verification system:
  - Made verification work with or without a configuration
  - Added basic validation for all tweets (content presence, length, image paths)
  - Made driver parameter optional to support content-only verification

## 2025-02-21

### Code Consolidation and Cleanup
- Removed duplicated functions from multiple files:
  - Moved `boldify` function to `utils/tweet.py` and updated imports
  - Removed local implementations from `z1_generate_tweet.py` and `a1_daily_update.py`
- Simplified tweet generation in `z1_generate_tweet.py`:
  - Updated to use the shared `boldify` function from `utils/tweet.py`
  - Maintained backward compatibility with existing tweet generation flow
- Improved code organization:
  - Centralized text formatting utilities in `utils/tweet.py`
  - Reduced code duplication across the codebase
  - Made formatting consistent across different tweet types

## 2025-03-08

### Enhanced Tweet Reply System
- Implemented multiple reply styles for the tweet replier workflow:
  - Added `TWEET_REPLY_FUNNY_USER_PROMPT` for generating humorous, light-hearted responses
  - Added `TWEET_REPLY_COMMONSENSE_USER_PROMPT` for generating responses based on common-sense insights
  - Enhanced the existing academic response system to work alongside new reply types
- Added corresponding functions in `utils/vector_store.py`:
  - `write_tweet_reply_funny()` for generating funny responses
  - `write_tweet_reply_commonsense()` for generating common-sense responses
- Updated the tweet replier notebook to handle all three response types:
  - Added conditional logic to select the appropriate reply function based on the response type
  - Maintained consistent formatting and extraction of responses across all types
- Improved documentation:
  - Updated STRUCTURE.md with details about the new tweet reply functions
  - Added comprehensive documentation for all new functions and prompts

## 2025-03-12

### Tweet Reply System Productionization
- Converted the tweet reply notebook workflow into a production script:
  - Created `executors/c1_tweet_reply.py` as a standalone executable script
  - Implemented robust error handling and logging throughout the workflow
  - Added clear function separation following the structure of other executor scripts
- Enhanced the tweet reply workflow:
  - Added proper metadata tracking for all reply types
  - Improved response type handling with clear defaults
  - Implemented comprehensive logging for each step of the process
- Structured the script with modular functions:
  - `get_recent_tweets()` for fetching and formatting recent tweets
  - `get_recent_discussions()` for retrieving recent tweet analyses
  - `get_previous_replies()` for obtaining context from previous replies
  - `select_tweet_to_reply()` for selecting an appropriate tweet to respond to
  - `find_related_content()` for retrieving relevant content from LLMpedia
  - `generate_reply()` for creating the appropriate type of response
  - `store_reply()` for saving the reply to the database
- Updated STRUCTURE.md to include the new script in the executors directory