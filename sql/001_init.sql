CREATE TABLE IF NOT EXISTS sessions (
  session_id    TEXT PRIMARY KEY,
  version       TEXT NOT NULL DEFAULT 'v1',
  rollout_group TEXT NOT NULL DEFAULT 'control',
  status        TEXT NOT NULL DEFAULT 'running',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  event_id    BIGSERIAL PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  seq         INT  NOT NULL,
  type        TEXT NOT NULL CHECK (type IN
              ('user_input','model_decision','tool_call','tool_result','approval','error')),
  source      TEXT NOT NULL,
  tool        TEXT,
  args        JSONB,
  result      JSONB,
  latency_ms  INT,
  tokens      JSONB,
  error       TEXT,
  truncated   BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, seq);
