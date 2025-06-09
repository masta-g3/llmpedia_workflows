CREATE TABLE IF NOT EXISTS tweet_analysis (
    id SERIAL PRIMARY KEY,
    tstp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    unique_tweets INTEGER NOT NULL,
    thinking_process TEXT,
    response TEXT,
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL  -- When analysis was posted (mirrors reddit_analysis.reported_at)
);