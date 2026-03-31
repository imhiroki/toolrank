-- ============================================================
-- ToolRank v17: Trust Infrastructure Migration
-- Adapts to existing 'servers' table (UUID primary keys)
-- ============================================================

-- 1. Selection Tournament Results (Layer 2)
CREATE TABLE IF NOT EXISTS selection_results (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  server_id     UUID NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  server_name   TEXT NOT NULL,
  model_used    TEXT NOT NULL DEFAULT 'claude-sonnet-4-20250514',
  total_rounds  INT NOT NULL DEFAULT 0,
  wins          INT NOT NULL DEFAULT 0,
  selection_rate DECIMAL(5,2) GENERATED ALWAYS AS (
    CASE WHEN total_rounds > 0 THEN (wins::DECIMAL / total_rounds * 100) ELSE 0 END
  ) STORED,
  task_categories JSONB DEFAULT '[]',
  competitor_ids  JSONB DEFAULT '[]',
  run_metadata    JSONB DEFAULT '{}',
  run_at        TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sel_server ON selection_results(server_id);
CREATE INDEX IF NOT EXISTS idx_sel_rate   ON selection_results(selection_rate DESC);

-- 2. Trust Tiers
CREATE TABLE IF NOT EXISTS trust_tiers (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  server_id     UUID NOT NULL UNIQUE REFERENCES servers(id) ON DELETE CASCADE,
  server_name   TEXT NOT NULL,

  spec_verified         TEXT DEFAULT 'none',
  spec_verified_at      TIMESTAMPTZ,
  spec_verified_score   DECIMAL(5,2),

  selection_verified       TEXT DEFAULT 'none',
  selection_verified_at    TIMESTAMPTZ,
  selection_verified_rate  DECIMAL(5,2),

  runtime_verified         TEXT DEFAULT 'none',
  runtime_verified_at      TIMESTAMPTZ,
  runtime_verified_data    JSONB DEFAULT '{}',

  trust_level   INT GENERATED ALWAYS AS (
    (CASE WHEN spec_verified = 'earned' THEN 1 ELSE 0 END) +
    (CASE WHEN selection_verified = 'earned' THEN 1 ELSE 0 END) +
    (CASE WHEN runtime_verified = 'earned' THEN 1 ELSE 0 END)
  ) STORED,

  spec_expires_at       TIMESTAMPTZ,
  selection_expires_at  TIMESTAMPTZ,
  runtime_expires_at    TIMESTAMPTZ,

  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trust_server ON trust_tiers(server_id);
CREATE INDEX IF NOT EXISTS idx_trust_level  ON trust_tiers(trust_level DESC);

-- 3. Trust Audit Log
CREATE TABLE IF NOT EXISTS trust_audit_log (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  server_id   UUID NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
  action      TEXT NOT NULL,
  tier_name   TEXT,
  old_value   TEXT,
  new_value   TEXT,
  reason      TEXT,
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_server ON trust_audit_log(server_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON trust_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time   ON trust_audit_log(created_at DESC);

-- 4. Gate Results (CI/CD history)
CREATE TABLE IF NOT EXISTS gate_results (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  server_id     UUID REFERENCES servers(id) ON DELETE SET NULL,
  repo_url      TEXT NOT NULL,
  gate_type     TEXT NOT NULL,
  passed        BOOLEAN NOT NULL,
  spec_score    DECIMAL(5,2),
  selection_rate DECIMAL(5,2),
  threshold_config JSONB DEFAULT '{}',
  details       JSONB DEFAULT '{}',
  triggered_by  TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gate_repo ON gate_results(repo_url);
CREATE INDEX IF NOT EXISTS idx_gate_type ON gate_results(gate_type);

-- 5. Add canonical/trust columns to existing servers table
ALTER TABLE servers ADD COLUMN IF NOT EXISTS is_canonical       BOOLEAN DEFAULT TRUE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS canonical_id       UUID REFERENCES servers(id);
ALTER TABLE servers ADD COLUMN IF NOT EXISTS is_test            BOOLEAN DEFAULT FALSE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS is_fork            BOOLEAN DEFAULT FALSE;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS fork_of            TEXT;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS maintenance_status TEXT DEFAULT 'active';
ALTER TABLE servers ADD COLUMN IF NOT EXISTS last_commit_at     TIMESTAMPTZ;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS github_stars       INT DEFAULT 0;
ALTER TABLE servers ADD COLUMN IF NOT EXISTS duplicate_group    TEXT;

-- 6. RLS for new tables
ALTER TABLE selection_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE trust_tiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE trust_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE gate_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read" ON selection_results FOR SELECT USING (true);
CREATE POLICY "Public read" ON trust_tiers FOR SELECT USING (true);
CREATE POLICY "Public read" ON trust_audit_log FOR SELECT USING (true);
CREATE POLICY "Public read" ON gate_results FOR SELECT USING (true);

CREATE POLICY "Service write" ON selection_results FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON trust_tiers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON trust_audit_log FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service write" ON gate_results FOR ALL USING (auth.role() = 'service_role');

-- 7. Update latest_scores view to include trust data
CREATE OR REPLACE VIEW latest_scores AS
SELECT DISTINCT ON (s.id)
  s.id AS server_id,
  s.server_name,
  s.display_name,
  s.source,
  s.category,
  s.tool_count,
  s.is_canonical,
  s.is_test,
  s.is_fork,
  s.maintenance_status,
  s.github_stars,
  sc.total_score,
  sc.findability,
  sc.clarity,
  sc.precision,
  sc.efficiency,
  sc.level,
  sc.level_name,
  sc.scanned_at,
  tt.trust_level,
  tt.spec_verified,
  tt.selection_verified,
  tt.selection_verified_rate,
  tt.runtime_verified
FROM servers s
JOIN scores sc ON sc.server_id = s.id
LEFT JOIN trust_tiers tt ON tt.server_id = s.id
ORDER BY s.id, sc.scanned_at DESC;

-- 8. Update category_rankings to filter non-canonical
CREATE OR REPLACE VIEW category_rankings AS
SELECT
  ls.*,
  RANK() OVER (PARTITION BY ls.category ORDER BY ls.total_score DESC) AS category_rank,
  COUNT(*) OVER (PARTITION BY ls.category) AS category_total
FROM latest_scores ls
WHERE ls.category IS NOT NULL
  AND ls.is_canonical = TRUE
  AND ls.is_test = FALSE;
