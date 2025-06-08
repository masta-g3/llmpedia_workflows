-- Create table for storing Reddit posts from LLM-related subreddits
CREATE TABLE IF NOT EXISTS reddit_posts (
    id SERIAL PRIMARY KEY,
    reddit_id TEXT UNIQUE NOT NULL,        -- Reddit post ID (e.g., "1a2b3c4")
    subreddit TEXT NOT NULL,               -- Source subreddit (e.g., "LocalLLaMA")
    title TEXT NOT NULL,                   -- Post title
    selftext TEXT,                         -- Post content (empty for link posts)
    author TEXT,                           -- Reddit username
    url TEXT,                              -- External URL if link post
    permalink TEXT NOT NULL,               -- Reddit permalink
    
    -- Timestamps following existing pattern
    tstp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- Collection timestamp
    post_timestamp TIMESTAMP WITHOUT TIME ZONE,                           -- When posted on Reddit
    
    -- Engagement metrics following existing pattern
    score INTEGER DEFAULT 0,              -- Upvotes - downvotes
    upvote_ratio REAL,                     -- Ratio of upvotes (0.0-1.0)
    num_comments INTEGER DEFAULT 0,       -- Comment count
    
    -- Boolean flags following existing pattern
    is_self BOOLEAN DEFAULT FALSE,         -- True if text post, False if link
    processed BOOLEAN DEFAULT FALSE,       -- Processing flag
    
    -- Additional Reddit-specific fields
    post_type TEXT,                        -- 'text', 'link', 'image', 'video'
    flair_text TEXT,                       -- Post flair if any
    arxiv_code TEXT,                       -- Extracted arxiv code if any (following tweet pattern)
    
    -- Metadata following existing pattern
    metadata JSONB                         -- Additional Reddit-specific data
);

-- Create indexes following llm_tweets pattern
CREATE INDEX IF NOT EXISTS reddit_posts_reddit_id_key ON reddit_posts(reddit_id);
CREATE INDEX IF NOT EXISTS reddit_posts_tstp_idx ON reddit_posts(tstp);
CREATE INDEX IF NOT EXISTS reddit_posts_post_timestamp_idx ON reddit_posts(post_timestamp);
CREATE INDEX IF NOT EXISTS reddit_posts_processed_idx ON reddit_posts(processed);
CREATE INDEX IF NOT EXISTS reddit_posts_subreddit_idx ON reddit_posts(subreddit);
CREATE INDEX IF NOT EXISTS reddit_posts_metrics_idx ON reddit_posts(score, num_comments);

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON reddit_posts TO public;
GRANT USAGE, SELECT ON SEQUENCE reddit_posts_id_seq TO public; 