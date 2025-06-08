-- Create table for storing Reddit comments with threading support
CREATE TABLE IF NOT EXISTS reddit_comments (
    id SERIAL PRIMARY KEY,
    reddit_id TEXT UNIQUE NOT NULL,       -- Comment ID
    post_reddit_id TEXT NOT NULL,         -- Parent post ID (references reddit_posts.reddit_id)
    parent_id TEXT,                       -- Parent comment ID (NULL for top-level)
    subreddit TEXT NOT NULL,              -- Source subreddit (denormalized for easier queries)
    author TEXT,                          -- Comment author
    body TEXT NOT NULL,                   -- Comment content
    
    -- Timestamps following existing pattern
    tstp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- Collection timestamp
    comment_timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,               -- When comment was posted
    
    -- Engagement metrics
    score INTEGER DEFAULT 0,              -- Comment score
    
    -- Comment hierarchy
    depth INTEGER DEFAULT 0,              -- Comment nesting level (0 = top-level)
    is_top_level BOOLEAN DEFAULT FALSE,   -- Quick flag for top-level comments
    
    -- Processing flag
    processed BOOLEAN DEFAULT FALSE,
    
    -- Additional comment-specific data
    metadata JSONB                        -- Additional comment-specific data
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS reddit_comments_reddit_id_key ON reddit_comments(reddit_id);
CREATE INDEX IF NOT EXISTS reddit_comments_post_id_idx ON reddit_comments(post_reddit_id);
CREATE INDEX IF NOT EXISTS reddit_comments_tstp_idx ON reddit_comments(tstp);
CREATE INDEX IF NOT EXISTS reddit_comments_comment_timestamp_idx ON reddit_comments(comment_timestamp);
CREATE INDEX IF NOT EXISTS reddit_comments_processed_idx ON reddit_comments(processed);
CREATE INDEX IF NOT EXISTS reddit_comments_subreddit_idx ON reddit_comments(subreddit);
CREATE INDEX IF NOT EXISTS reddit_comments_score_idx ON reddit_comments(score);
CREATE INDEX IF NOT EXISTS reddit_comments_depth_idx ON reddit_comments(depth);

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON reddit_comments TO public;
GRANT USAGE, SELECT ON SEQUENCE reddit_comments_id_seq TO public; 