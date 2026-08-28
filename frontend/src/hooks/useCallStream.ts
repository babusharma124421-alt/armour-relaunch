import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchJson, websocketUrl, type Breakdown, type RiskPayload, type Verdict } from '../lib/api'

export type StreamStatus = 'idle' | 'requesting_permission' | 'listening' | 'analyzing' | 'error'

export interface CallStreamState {
  status: StreamStatus
  currentScore: number
  verdict: Verdict | null
  reasons: string[]
  matchedPatterns: string[]
  transcript: string
  detectedLanguage: string
  sessionId: string | null
  breakdown: Breakdown | null
  error: string | null
}

export interface UseCallStreamOptions {
  isPractice?: boolean
  practiceScript?: string
  practicePayloads?: RiskPayload[]
}

interface SessionResponse {
  session_id: string
  language: string
}

const initialState: CallStreamState = {
  status: 'idle',
  currentScore: 0,
  verdict: null,
  reasons: [],
  matchedPatterns: [],
  transcript: '',
  detectedLanguage: 'unknown',
  sessionId: null,
  breakdown: null,
  error: null,
}

function languageForBackend(language: string): string {
  return language.toLowerCase().startsWith('hi') ? 'hi' : 'en'
}

function fallbackPracticePayloads(script: string): RiskPayload[] {
  const normalized = script.toLowerCase()
  const critical = /(cbi|aadhaar|money laundering|arrest|otp|safe account|गिरफ्तार|ओटीपी)/u.test(normalized)
  const medium = /(sim|deactivat|kyc|सिम|केवाईसी)/u.test(normalized)
  const finalScore = critical ? 88 : medium ? 48 : 12
  const verdict: Verdict = finalScore > 70 ? 'CRITICAL' : finalScore >= 30 ? 'SUSPICIOUS' : 'SAFE'
  const matchedPatterns = critical
    ? ['authority_claim_en', 'arrest_threat_en', 'money_transfer_en', 'secrecy_request_en']
    : medium
      ? ['sim_deactivation_en', 'urgency_deadline_en']
      : []
  return [0.5, 0.75, 1].map((progress) => {
    const score = Math.round(finalScore * progress)
    const stepVerdict: Verdict = score > 70 ? 'CRITICAL' : score >= 30 ? 'SUSPICIOUS' : 'SAFE'
    return {
      voice_score: critical ? 35 : 12,
      script_score: score,
      intent_score: score,
      caller_score: 0,
      behavior_score: Math.round(score * 0.8),
      final_score: score,
      verdict: stepVerdict,
      reasons: matchedPatterns.length > 0 ? ['This fictional script contains recognizable social-engineering signals.'] : ['No strong scam indicators were detected in this practice script.'],
      matched_patterns: matchedPatterns,
      transcript_snippet: script.slice(-280),
      detected_language: /[\u0900-\u097f]/u.test(script) ? 'hi' : 'en',
      breakdown: {
        voice: critical ? 35 : 12,
        intent: score,
        caller: 0,
        behavior: Math.round(score * 0.8),
      },
    }
  })
}

export function useCallStream(options: UseCallStreamOptions = {}) {
  const { isPractice = false, practiceScript = '', practicePayloads = [] } = options
  const { i18n, t } = useTranslation()
  const [state, setState] = useState<CallStreamState>(initialState)
  const socketRef = useRef<WebSocket | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const practiceTimerRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const stoppedRef = useRef(true)
  const mountedRef = useRef(true)
  const sessionIdRef = useRef<string | null>(null)

  const setSafeState = useCallback((update: Partial<CallStreamState>) => {
    if (mountedRef.current) setState((current) => ({ ...current, ...update }))
  }, [])

  const cleanupTransport = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (practiceTimerRef.current !== null) {
      window.clearInterval(practiceTimerRef.current)
      practiceTimerRef.current = null
    }
    if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop()
    recorderRef.current = null
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
    if (socketRef.current && socketRef.current.readyState < WebSocket.CLOSING) socketRef.current.close()
    socketRef.current = null
  }, [])

  const applyPayload = useCallback((payload: RiskPayload) => {
    setSafeState({
      status: 'analyzing',
      currentScore: payload.final_score,
      verdict: payload.verdict,
      reasons: payload.reasons,
      matchedPatterns: payload.matched_patterns,
      transcript: payload.transcript_snippet,
      detectedLanguage: payload.detected_language,
      breakdown: payload.breakdown,
      error: null,
    })
    window.setTimeout(() => setSafeState({ status: 'listening' }), 260)
  }, [setSafeState])

  const replayPractice = useCallback((sessionId: string) => {
    const payloads = practicePayloads.length > 0 ? practicePayloads : fallbackPracticePayloads(practiceScript)
    let index = 0
    setSafeState({ status: 'listening', error: null })
    practiceTimerRef.current = window.setInterval(() => {
      const payload = payloads[index]
      if (!payload) {
        if (practiceTimerRef.current !== null) window.clearInterval(practiceTimerRef.current)
        practiceTimerRef.current = null
        setSafeState({ status: 'idle', sessionId })
        return
      }
      applyPayload(payload)
      index += 1
      if (index >= payloads.length && practiceTimerRef.current !== null) {
        window.clearInterval(practiceTimerRef.current)
        practiceTimerRef.current = null
        window.setTimeout(() => setSafeState({ status: 'idle' }), 450)
      }
    }, 900)
  }, [applyPayload, practicePayloads, practiceScript, setSafeState])

  const startInternal = useCallback(async (isReconnect: boolean) => {
    stoppedRef.current = false
    setSafeState({ status: isPractice && !isReconnect ? 'requesting_permission' : 'requesting_permission', error: null })
    const language = languageForBackend(i18n.language)
    let stream: MediaStream | undefined
    const shouldUseRealPracticeAudio = import.meta.env.VITE_PRACTICE_USE_REAL_AUDIO === 'true'
    try {
      if (!isPractice || shouldUseRealPracticeAudio) {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error(t('call.permission'))
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        mediaStreamRef.current = stream
      }
      const session = await fetchJson<SessionResponse>('/session/start', {
        method: 'POST',
        body: JSON.stringify({ language, is_practice: isPractice }),
      })
      sessionIdRef.current = session.session_id
      setSafeState({ sessionId: session.session_id, error: null })

      if (isPractice && !shouldUseRealPracticeAudio) {
        replayPractice(session.session_id)
        return
      }

      const socket = new WebSocket(websocketUrl(`/ws/call/${session.session_id}`))
      socket.binaryType = 'arraybuffer'
      socketRef.current = socket
      socket.onopen = () => {
        if (!stream) return
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm'
        const recorder = new MediaRecorder(stream, { mimeType })
        recorderRef.current = recorder
        recorder.ondataavailable = (event: BlobEvent) => {
          if (event.data.size === 0 || socket.readyState !== WebSocket.OPEN) return
          void event.data.arrayBuffer().then((buffer) => {
            if (socket.readyState === WebSocket.OPEN) socket.send(buffer)
          })
        }
        recorder.start(2000)
        setSafeState({ status: 'listening' })
      }
      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          applyPayload(JSON.parse(event.data) as RiskPayload)
        } catch {
          setSafeState({ status: 'error', error: t('call.error') })
        }
      }
      socket.onerror = () => {
        setSafeState({ status: 'error', error: t('call.error') })
      }
      socket.onclose = () => {
        if (stoppedRef.current) return
        setSafeState({ status: 'error', error: t('call.error') })
        if (reconnectAttemptsRef.current < 1) {
          reconnectAttemptsRef.current += 1
          reconnectTimerRef.current = window.setTimeout(() => {
            reconnectTimerRef.current = null
            void startInternal(true)
          }, 3000)
        }
      }
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop())
      if (isPractice && !shouldUseRealPracticeAudio) {
        const localSessionId = sessionIdRef.current ?? `practice-${Date.now()}`
        sessionIdRef.current = localSessionId
        setSafeState({ sessionId: localSessionId, error: null })
        replayPractice(localSessionId)
        return
      }
      setSafeState({ status: 'error', error: error instanceof Error ? error.message : t('call.error') })
    }
  }, [applyPayload, i18n.language, isPractice, replayPractice, setSafeState, t])

  const startSession = useCallback(() => {
    reconnectAttemptsRef.current = 0
    cleanupTransport()
    void startInternal(false)
  }, [cleanupTransport, startInternal])

  const stopSession = useCallback(() => {
    stoppedRef.current = true
    cleanupTransport()
    setSafeState({ status: 'idle' })
  }, [cleanupTransport, setSafeState])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      stoppedRef.current = true
      cleanupTransport()
    }
  }, [cleanupTransport])

  return {
    ...state,
    startSession,
    stopSession,
  }
}
