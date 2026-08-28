export type Verdict = 'SAFE' | 'SUSPICIOUS' | 'CRITICAL'

export interface Breakdown {
  voice: number
  intent: number
  caller: number
  behavior: number
}

export interface RiskPayload {
  voice_score: number
  script_score: number
  intent_score: number
  caller_score: number
  behavior_score: number
  final_score: number
  verdict: Verdict
  reasons: string[]
  matched_patterns: string[]
  transcript_snippet: string
  detected_language: string
  breakdown: Breakdown
}

export interface SessionSummary {
  id: string
  created_at: string
  verdict: Verdict | null
  final_score: number | null
  language: string
  alert_sent: boolean
  is_practice: boolean
}

export interface SessionHistory {
  session: SessionSummary
  events: RiskPayload[]
}

export interface Helpline {
  id?: string
  name: string
  number: string
  category: string
  description?: string | null
  available_hours?: string | null
  locale?: string
}

export interface EmergencyContact {
  id: string
  user_session_owner_id: string
  name: string
  phone: string
  relationship?: string | null
}

function isLocalhost(value: string): boolean {
  try {
    const parsed = new URL(value)
    return parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1' || parsed.hostname === '0.0.0.0'
  } catch {
    return false
  }
}

export function getHttpBaseUrl(): string {
  const configured = import.meta.env.VITE_BACKEND_HTTP_URL?.trim()
  if (configured && (typeof window === 'undefined' || window.location.hostname === 'localhost' || !isLocalhost(configured))) {
    return configured.replace(/\/$/, '')
  }
  return '/api'
}

export function getWebSocketBaseUrl(): string {
  const configured = import.meta.env.VITE_BACKEND_WS_URL?.trim()
  if (configured && (typeof window === 'undefined' || window.location.hostname === 'localhost' || !isLocalhost(configured))) {
    return configured.replace(/\/$/, '')
  }
  return '/api'
}

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${getHttpBaseUrl()}${normalizedPath}`
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(apiUrl(path), { ...init, headers })
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Keep the status-based message when the server returned no JSON.
    }
    throw new Error(detail)
  }
  return (await response.json()) as T
}

export function getDeviceId(): string {
  const storageKey = 'the_app_device_id'
  const existing = window.localStorage.getItem(storageKey)
  if (existing) return existing
  const generated = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  window.localStorage.setItem(storageKey, generated)
  return generated
}

export function websocketUrl(path: string): string {
  const base = getWebSocketBaseUrl()
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  if (base.startsWith('/')) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${base}${normalizedPath}`
  }
  return `${base}${normalizedPath}`
}
