-- Create the pending_tweets table to store generated tweet candidates
CREATE TABLE IF NOT EXISTS pending_tweets (
    id SERIAL PRIMARY KEY,
    arxiv_code VARCHAR NOT NULL,
    tweet_type VARCHAR NOT NULL,
    thread_data_json TEXT NOT NULL,  -- Stores the TweetThread model dump
    status VARCHAR NOT NULL DEFAULT 'pending',
    generation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    selection_timestamp TIMESTAMP NULL,
    posting_timestamp TIMESTAMP NULL
);

-- Add an index for faster lookups by status
CREATE INDEX IF NOT EXISTS idx_pending_tweets_status ON pending_tweets (arxiv_code, status); 