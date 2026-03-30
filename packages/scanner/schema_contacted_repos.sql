-- ToolRank: contacted_repos table
-- Run this in Supabase SQL Editor to enable auto-issue cooldown tracking.

CREATE TABLE IF NOT EXISTS contacted_repos (
  id SERIAL PRIMARY KEY,
  repo_name TEXT NOT NULL UNIQUE,
  server_name TEXT,
  score_at_contact REAL,
  contacted_at TIMESTAMPTZ DEFAULT NOW(),
  issue_url TEXT
);

-- Index for fast lookup by repo_name
CREATE INDEX IF NOT EXISTS idx_contacted_repos_name ON contacted_repos(repo_name);

-- Enable upsert on repo_name
ALTER TABLE contacted_repos ADD CONSTRAINT contacted_repos_repo_unique UNIQUE (repo_name);
