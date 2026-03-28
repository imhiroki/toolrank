-- ToolRank Score Database Schema
-- Run in Supabase SQL Editor to create tables

-- Servers table: MCP servers from registries
CREATE TABLE IF NOT EXISTS servers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,  -- 'smithery', 'mcp-registry', 'npm'
  server_name TEXT NOT NULL,
  display_name TEXT,
  description TEXT,
  category TEXT,
  url TEXT,
  repository_url TEXT,
  is_verified BOOLEAN DEFAULT FALSE,
  is_deployed BOOLEAN DEFAULT FALSE,
  tool_count INTEGER DEFAULT 0,
  raw_data JSONB,
  first_seen_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source, server_name)
);

-- Tools table: individual MCP tools
CREATE TABLE IF NOT EXISTS tools (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  server_id UUID REFERENCES servers(id) ON DELETE CASCADE,
  tool_name TEXT NOT NULL,
  description TEXT,
  input_schema JSONB,
  raw_definition JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(server_id, tool_name)
);

-- Scores table: ToolRank Score snapshots (time series = the moat)
CREATE TABLE IF NOT EXISTS scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
  server_id UUID REFERENCES servers(id) ON DELETE CASCADE,
  
  -- 4 dimension scores
  findability REAL NOT NULL DEFAULT 0,
  clarity REAL NOT NULL DEFAULT 0,
  precision REAL NOT NULL DEFAULT 0,
  efficiency REAL NOT NULL DEFAULT 0,
  total_score REAL NOT NULL DEFAULT 0,
  
  -- Maturity level (0-4)
  level INTEGER NOT NULL DEFAULT 0,
  level_name TEXT NOT NULL DEFAULT 'Absent',
  
  -- Scoring method
  scoring_level TEXT NOT NULL DEFAULT 'A',  -- 'A' (rule), 'B' (embedding), 'C' (LLM)
  
  scanned_at TIMESTAMPTZ DEFAULT NOW()
);

-- Issues table: specific problems found
CREATE TABLE IF NOT EXISTS issues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  score_id UUID REFERENCES scores(id) ON DELETE CASCADE,
  tool_id UUID REFERENCES tools(id) ON DELETE CASCADE,
  
  dimension TEXT NOT NULL,  -- 'findability', 'clarity', 'precision', 'efficiency'
  category TEXT NOT NULL,
  severity TEXT NOT NULL,  -- 'critical', 'warning', 'info'
  message TEXT NOT NULL,
  fix_suggestion TEXT,
  estimated_impact INTEGER DEFAULT 0,
  
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scan summaries: daily scan metadata
CREATE TABLE IF NOT EXISTS scan_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,
  scan_date DATE NOT NULL DEFAULT CURRENT_DATE,
  
  total_servers INTEGER DEFAULT 0,
  scored_servers INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  avg_score REAL DEFAULT 0,
  
  -- Score distribution
  dominant_count INTEGER DEFAULT 0,  -- 85+
  preferred_count INTEGER DEFAULT 0, -- 70-84
  selectable_count INTEGER DEFAULT 0, -- 50-69
  visible_count INTEGER DEFAULT 0,    -- 25-49
  absent_count INTEGER DEFAULT 0,     -- 0-24
  
  raw_summary JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source, scan_date)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_scores_server_date ON scores(server_id, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_servers_category ON servers(category);
CREATE INDEX IF NOT EXISTS idx_servers_source ON servers(source);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_scan_summaries_date ON scan_summaries(scan_date DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_summaries ENABLE ROW LEVEL SECURITY;

-- Public read access (scores are public data)
CREATE POLICY "Public read" ON servers FOR SELECT USING (true);
CREATE POLICY "Public read" ON tools FOR SELECT USING (true);
CREATE POLICY "Public read" ON scores FOR SELECT USING (true);
CREATE POLICY "Public read" ON issues FOR SELECT USING (true);
CREATE POLICY "Public read" ON scan_summaries FOR SELECT USING (true);

-- Service role write access (scanner uses service key)
CREATE POLICY "Service write" ON servers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON tools FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON scores FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON issues FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON scan_summaries FOR ALL USING (auth.role() = 'service_role');

-- View: Latest scores per server (for ranking pages)
CREATE OR REPLACE VIEW latest_scores AS
SELECT DISTINCT ON (s.id)
  s.id AS server_id,
  s.server_name,
  s.display_name,
  s.source,
  s.category,
  s.tool_count,
  sc.total_score,
  sc.findability,
  sc.clarity,
  sc.precision,
  sc.efficiency,
  sc.level,
  sc.level_name,
  sc.scanned_at
FROM servers s
JOIN scores sc ON sc.server_id = s.id
ORDER BY s.id, sc.scanned_at DESC;

-- View: Category rankings
CREATE OR REPLACE VIEW category_rankings AS
SELECT
  ls.*,
  RANK() OVER (PARTITION BY ls.category ORDER BY ls.total_score DESC) AS category_rank,
  COUNT(*) OVER (PARTITION BY ls.category) AS category_total
FROM latest_scores ls
WHERE ls.category IS NOT NULL;
