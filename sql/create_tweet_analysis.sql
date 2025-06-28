CREATE TABLE IF NOT EXISTS tweet_analysis (
    id SERIAL PRIMARY KEY,
    tstp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    unique_tweets INTEGER NOT NULL,
    thinking_process TEXT,
    response TEXT,
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,  -- When analysis was posted (mirrors reddit_analysis.reported_at)
    referenced_tweets JSONB DEFAULT NULL  -- Referenced tweets metadata
);

-- Create GIN index for efficient JSONB querying
CREATE INDEX IF NOT EXISTS tweet_analysis_references_gin 
ON tweet_analysis USING gin (referenced_tweets);

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON tweet_analysis TO public;
GRANT USAGE, SELECT ON SEQUENCE tweet_analysis_id_seq TO public;