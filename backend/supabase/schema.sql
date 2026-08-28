-- Armour voice-integrity platform schema.
-- Run this complete file in a fresh Supabase/Postgres project.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  verdict       TEXT CHECK (verdict IN ('SAFE', 'SUSPICIOUS', 'CRITICAL')),
  final_score   FLOAT CHECK (final_score IS NULL OR (final_score >= 0 AND final_score <= 100)),
  language      TEXT NOT NULL DEFAULT 'auto',
  alert_sent    BOOLEAN NOT NULL DEFAULT FALSE,
  is_practice   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS call_events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  timestamp           TIMESTAMPTZ NOT NULL DEFAULT now(),
  voice_score         FLOAT CHECK (voice_score IS NULL OR (voice_score >= 0 AND voice_score <= 100)),
  script_score        FLOAT CHECK (script_score IS NULL OR (script_score >= 0 AND script_score <= 100)),
  intent_score        FLOAT CHECK (intent_score IS NULL OR (intent_score >= 0 AND intent_score <= 100)),
  behavior_score      FLOAT CHECK (behavior_score IS NULL OR (behavior_score >= 0 AND behavior_score <= 100)),
  final_score         FLOAT CHECK (final_score IS NULL OR (final_score >= 0 AND final_score <= 100)),
  verdict             TEXT CHECK (verdict IS NULL OR verdict IN ('SAFE', 'SUSPICIOUS', 'CRITICAL')),
  transcript_snippet  TEXT CHECK (transcript_snippet IS NULL OR char_length(transcript_snippet) <= 280),
  matched_patterns    TEXT[] NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_call_events_session ON call_events(session_id);
CREATE INDEX IF NOT EXISTS idx_call_events_timestamp ON call_events(timestamp DESC);

CREATE TABLE IF NOT EXISTS caller_reputation (
  phone_number_hash       TEXT PRIMARY KEY,
  report_count            INT NOT NULL DEFAULT 0 CHECK (report_count >= 0),
  community_report_count  INT NOT NULL DEFAULT 0 CHECK (community_report_count >= 0),
  avg_reported_risk       FLOAT NOT NULL DEFAULT 0.0 CHECK (avg_reported_risk >= 0 AND avg_reported_risk <= 1),
  last_seen               TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'report_category') THEN
    CREATE TYPE report_category AS ENUM (
      'impersonation',
      'financial_fraud',
      'harassment',
      'other'
    );
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS community_reports (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone_number_hash   TEXT NOT NULL REFERENCES caller_reputation(phone_number_hash),
  reporter_session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  category            report_category NOT NULL,
  note                TEXT CHECK (note IS NULL OR char_length(note) <= 1000),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_community_reports_phone_hash ON community_reports(phone_number_hash);
CREATE INDEX IF NOT EXISTS idx_community_reports_created_at ON community_reports(created_at DESC);

CREATE TABLE IF NOT EXISTS emergency_contacts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_session_owner_id TEXT NOT NULL,
  name                  TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 100),
  phone                 TEXT NOT NULL CHECK (char_length(phone) BETWEEN 7 AND 32),
  relationship          TEXT CHECK (relationship IS NULL OR char_length(relationship) <= 80)
);
CREATE INDEX IF NOT EXISTS idx_emergency_contacts_owner ON emergency_contacts(user_session_owner_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_emergency_contacts_owner_phone
  ON emergency_contacts(user_session_owner_id, phone);

CREATE TABLE IF NOT EXISTS helplines (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  number          TEXT NOT NULL,
  category        TEXT NOT NULL,
  description     TEXT,
  available_hours TEXT,
  locale          TEXT NOT NULL DEFAULT 'all',
  CONSTRAINT helplines_name_number_unique UNIQUE (name, number)
);
CREATE INDEX IF NOT EXISTS idx_helplines_category ON helplines(category);

INSERT INTO helplines (name, number, category, description, available_hours, locale)
VALUES
  ('National Cyber Crime Helpline', '1930', 'cybercrime', 'Report online financial fraud and cybercrime incidents.', '24x7', 'all'),
  ('National Cyber Crime Reporting Portal', 'cybercrime.gov.in', 'cybercrime', 'File an online cybercrime complaint and track its status.', 'Online portal', 'all'),
  ('RBI Banking Ombudsman', '14440', 'banking', 'Get help with unresolved banking service complaints.', 'Business hours', 'all'),
  ('Police Emergency', '100', 'emergency', 'Immediate police assistance in an emergency.', '24x7', 'all'),
  ('National Consumer Helpline', '1800-11-4000', 'consumer', 'Consumer protection guidance and complaint support.', '08:00–20:00', 'all'),
  ('Childline India', '1098', 'child_safety', 'Emergency support for children in distress.', '24x7', 'all'),
  ('Elderline', '14567', 'senior_citizens', 'Support and guidance for senior citizens.', '08:00–20:00', 'all')
ON CONFLICT (name, number) DO NOTHING;
