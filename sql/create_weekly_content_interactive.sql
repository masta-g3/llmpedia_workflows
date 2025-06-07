CREATE TABLE IF NOT EXISTS weekly_content_interactive (
    id SERIAL PRIMARY KEY,
    tstp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date DATE NOT NULL,
    content TEXT,
    interactive_components TEXT,
    metadata TEXT,
    layout_config TEXT,
    content_type VARCHAR(50) DEFAULT 'interactive_weekly_review'
);