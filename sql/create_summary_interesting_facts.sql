CREATE TABLE IF NOT EXISTS summary_interesting_facts (
    id SERIAL PRIMARY KEY,
    arxiv_code VARCHAR(20) NOT NULL,
    fact_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    tstp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_arxiv_fact UNIQUE (arxiv_code, fact_id)
);

-- Comment on table and columns for documentation
COMMENT ON TABLE summary_interesting_facts IS 'Stores interesting facts extracted from research papers';
COMMENT ON COLUMN summary_interesting_facts.arxiv_code IS 'The unique arxiv identifier for the paper';
COMMENT ON COLUMN summary_interesting_facts.fact_id IS 'The sequential ID of the fact (1-5) for a given paper';
COMMENT ON COLUMN summary_interesting_facts.fact IS 'The interesting fact extracted from the paper';
COMMENT ON COLUMN summary_interesting_facts.tstp IS 'Timestamp when the record was created'; 