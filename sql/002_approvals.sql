-- 高风险动作人工审批记录
CREATE TABLE IF NOT EXISTS approvals (
  id          BIGSERIAL PRIMARY KEY,
  session_id  TEXT NOT NULL,
  tool        TEXT NOT NULL,
  args        JSONB,
  decision    TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
  note        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approvals_session ON approvals(session_id, created_at);
