# the app — System Architecture

## Live Detection Pipeline
Audio (2s chunks via MediaRecorder)
  → [Browser] WebSocket binary stream
  → [FastAPI WS Handler] session_state manager
  → CONCURRENT:
      [VoiceAuthenticityService] RawNet2/HF → synthetic_probability
      [IntentAnalysisService / Whisper-Groq] → transcript + lang
  → [ScriptScannerService] regex patterns → script_score (offline, fast)
  → [IntentAnalysisService / Llama3-Groq] → llm_intent_score
  → combined_intent = 0.4*script + 0.6*llm
  → [BehaviorScoringService] XGBoost on session metadata → behavior_score
  → [FusionService] weighted sum → final_score + verdict
  → [Supabase] async log call_event
  → [WebSocket] RiskPayload JSON → React UI state

## Verdict Thresholds
  < 30: SAFE (green)  |  30-70: SUSPICIOUS (yellow)  |  > 70: CRITICAL (red)

## Fusion Weights
  Voice 20% · Intent 40% (script 40% + LLM 60% within intent)
  · Caller 20% · Behavior 20%

## Alert & Panic Flow
  CRITICAL verdict or manual Panic Button
  → POST /panic → AlertService (Twilio or Fast2SMS)
  → SMS to saved emergency contacts
  → Session flagged alert_sent=true in Supabase

## Helpline Surfacing
  CRITICAL overlay → "Report to 1930" → tel:1930 (one tap)
  /helplines → filterable directory from Supabase helplines table

## History & Evidence
  /history → paginated session list → expanded score-over-time chart
  Each session stores: verdict, final_score, call_events (scores +
  transcript snippets, no raw audio), alert_sent flag

## Education Module (parallel, non-live)
  /learn → Awareness Cards (JSON content, localized EN/HI)
  /quiz → 7-question scam red-flag quiz (JSON content, localized)
  /practice → Scam simulation: pre-scripted text → same live pipeline
    → "What Triggered This?" post-analysis panel

## Privacy Guarantees
  No raw audio stored. Phone numbers as SHA-256 hashes only.
  Transcript snippets max 280 chars. Rate limits on report + panic.
