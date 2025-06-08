-- Create table for storing Reddit analysis results
CREATE TABLE IF NOT EXISTS reddit_analysis (
    id SERIAL PRIMARY KEY,
    
    -- Timestamps following tweet_analysis pattern
    tstp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- Analysis creation time
    start_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,                      -- Analysis period start
    end_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,                        -- Analysis period end
    
    -- Reddit-specific analysis scope
    subreddit TEXT NOT NULL,               -- Primary subreddit analyzed (can be 'multi' for cross-subreddit)
    unique_posts INTEGER NOT NULL,         -- Number of unique posts analyzed
    total_comments INTEGER NOT NULL,       -- Total comments analyzed
    top_posts_analyzed INTEGER NOT NULL,   -- Number of top posts included in analysis
    
    -- Analysis content following tweet_analysis pattern
    thinking_process TEXT,                 -- Internal LLM reasoning
    response TEXT,                         -- Main analysis content
    
    -- Report tracking (mirrors tweet_analysis.posted_at pattern)
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,  -- When analysis was posted to X.com
    
    -- Reddit-specific analysis metadata
    subreddits_analyzed JSONB,            -- List of subreddits if multi-subreddit analysis
    themes JSONB,                         -- Extracted themes and trends
    top_posts JSONB,                      -- Top posts data for reference
    engagement_metrics JSONB,             -- Aggregated engagement statistics
    metadata JSONB                        -- Additional analysis metadata
);

-- Create indexes following tweet_analysis pattern  
CREATE INDEX IF NOT EXISTS reddit_analysis_tstp_idx ON reddit_analysis(tstp);
CREATE INDEX IF NOT EXISTS reddit_analysis_subreddit_idx ON reddit_analysis(subreddit);
CREATE INDEX IF NOT EXISTS reddit_analysis_period_idx ON reddit_analysis(start_date, end_date);
CREATE INDEX IF NOT EXISTS reddit_analysis_posted_at_idx ON reddit_analysis(posted_at) WHERE posted_at IS NULL;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON reddit_analysis TO public;
GRANT USAGE, SELECT ON SEQUENCE reddit_analysis_id_seq TO public; 