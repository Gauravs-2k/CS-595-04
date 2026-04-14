CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id TEXT NOT NULL,
  patient_name TEXT,
  patient_dob TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  sources JSONB,
  discharge_entities JSONB,
  pcp_entities JSONB
);

CREATE TABLE gaps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
  category TEXT,
  severity TEXT,
  title TEXT,
  description TEXT,
  source_text TEXT,
  source_line INT,
  standard_code TEXT,
  standard_system TEXT,
  suggested_action TEXT,
  resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMPTZ
);
