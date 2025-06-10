-- Add posted_at column to track when tweet analyses have been posted to X.com
-- This prevents duplicate posting and provides posting timestamps in PST

ALTER TABLE tweet_analysis 
ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- Index for faster lookups of unposted analyses
CREATE INDEX IF NOT EXISTS idx_tweet_analysis_posted_at ON tweet_analysis(posted_at) WHERE posted_at IS NULL; 