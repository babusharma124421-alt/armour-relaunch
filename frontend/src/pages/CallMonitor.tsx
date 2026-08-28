import { Activity, ChevronRight, CircleStop, Mic, ShieldCheck, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PanicButton } from '../components/PanicButton'
import { RiskGauge } from '../components/RiskGauge'
import { VerdictOverlay } from '../components/VerdictOverlay'
import { useCallStream } from '../hooks/useCallStream'
import { fetchJson, getDeviceId } from '../lib/api'

interface PanicResponse {
  notified_count: number
  success: boolean
}

function statusKey(status: ReturnType<typeof useCallStream>['status']): string {
  if (status === 'listening') return 'status.listening'
  if (status === 'analyzing') return 'status.analyzing'
  if (status === 'requesting_permission') return 'status.requesting_permission'
  if (status === 'error') return 'status.error'
  return 'status.idle'
}

export function CallMonitor() {
  const { t } = useTranslation()
  const stream = useCallStream()
  const [alertSent, setAlertSent] = useState(false)
  const [criticalDismissed, setCriticalDismissed] = useState(false)
  const [suspiciousDismissed, setSuspiciousDismissed] = useState(false)

  useEffect(() => {
    setAlertSent(false)
    setCriticalDismissed(false)
    setSuspiciousDismissed(false)
  }, [stream.sessionId, stream.currentScore, stream.verdict])

  const sendAlert = async () => {
    if (!stream.sessionId) {
      window.alert(t('panic.none'))
      return
    }
    try {
      const response = await fetchJson<PanicResponse>('/panic', {
        method: 'POST',
        body: JSON.stringify({ session_id: stream.sessionId, user_session_owner_id: getDeviceId() }),
      })
      if (!response.success) throw new Error('alert failed')
      setAlertSent(true)
      window.alert(t('panic.sent'))
    } catch {
      window.alert(t('panic.failed'))
    }
  }

  const running = stream.status === 'listening' || stream.status === 'analyzing' || stream.status === 'requesting_permission'
  const statusColor = stream.status === 'listening' ? 'text-risk-safe border-risk-safe/30 bg-risk-safe/10' : stream.status === 'error' ? 'text-risk-critical border-risk-critical/30 bg-risk-critical/10' : 'text-sky-300 border-sky-400/30 bg-sky-400/10'
  const visibleVerdict = stream.verdict === 'CRITICAL' && criticalDismissed ? null : stream.verdict === 'SUSPICIOUS' && suspiciousDismissed ? null : stream.verdict

  return (
    <div className="page-shell">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Live protection</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('nav.call')}</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">{t('app.subtitle')}</p>
        </div>
        <Link to="/practice" className="secondary-button px-3 py-2 text-sm"><Activity className="h-4 w-4 text-yellow-300" />{t('nav.practice')}<ChevronRight className="h-4 w-4" /></Link>
      </div>

      <section className="glass-panel rounded-3xl p-5 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className={`status-pulse inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-bold uppercase tracking-wider ${statusColor}`} aria-live="polite">
            <span className={`h-2 w-2 rounded-full ${stream.status === 'listening' ? 'bg-risk-safe' : stream.status === 'error' ? 'bg-risk-critical' : 'bg-sky-300'}`} />
            {t(statusKey(stream.status))}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500"><ShieldCheck className="h-4 w-4 text-sky-300" />{t('call.live_note')}</div>
        </div>

        <div className="mt-8 grid items-center gap-8 lg:grid-cols-[minmax(280px,380px)_1fr]">
          <div className="flex flex-col items-center">
            <RiskGauge score={stream.currentScore} verdict={stream.verdict} />
            <p className="mt-5 text-center text-sm text-slate-400">{stream.status === 'idle' ? t('call.idle') : stream.status === 'listening' ? t('call.listening') : stream.status === 'analyzing' ? t('call.analyzing') : stream.error ?? t('call.error')}</p>
            <button type="button" onClick={running ? stream.stopSession : stream.startSession} disabled={stream.status === 'requesting_permission'} className={`mt-5 min-w-52 rounded-2xl px-6 py-4 text-base font-bold transition disabled:cursor-wait disabled:opacity-60 ${running ? 'border border-red-400/40 bg-red-500/10 text-red-200 hover:bg-red-500/20' : 'bg-sky-400 text-slate-950 hover:bg-sky-300'}`}>
              {running ? <span className="inline-flex items-center gap-2"><CircleStop className="h-5 w-5" />{t('call.stop')}</span> : <span className="inline-flex items-center gap-2"><Mic className="h-5 w-5" />{t('call.start')}</span>}
            </button>
          </div>

          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4"><p className="text-xs uppercase tracking-wider text-slate-500">{t('call.detected_language')}</p><p className="mt-2 text-lg font-semibold uppercase text-white">{stream.detectedLanguage === 'unknown' ? t('common.unknown') : stream.detectedLanguage}</p></div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4"><p className="text-xs uppercase tracking-wider text-slate-500">Verdict</p><p className="mt-2 text-lg font-semibold text-white">{stream.verdict ? t(`verdict.${stream.verdict.toLowerCase()}`) : '—'}</p></div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
              <div className="flex items-center justify-between gap-4"><h2 className="text-sm font-semibold text-slate-200">{t('call.reason_heading')}</h2><span className="text-xs text-slate-500">{stream.reasons.length}/5</span></div>
              {stream.reasons.length > 0 ? <ul className="mt-4 max-h-36 space-y-2 overflow-y-auto pr-1">{stream.reasons.map((reason) => <li key={reason} className="flex items-start gap-3 rounded-xl bg-slate-900/70 px-3 py-2 text-sm leading-5 text-slate-300"><span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${stream.verdict === 'CRITICAL' ? 'bg-risk-critical' : stream.verdict === 'SUSPICIOUS' ? 'bg-risk-suspicious' : 'bg-risk-safe'}`} />{reason}</li>)}</ul> : <p className="mt-4 text-sm text-slate-500">{t('call.no_reasons')}</p>}
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4"><p className="text-xs uppercase tracking-wider text-slate-500">{t('call.transcript')}</p><p className="mt-2 min-h-12 text-sm italic leading-6 text-slate-400">{stream.transcript || t('call.no_transcript')}</p></div>
            {stream.error && <div className="flex items-start gap-3 rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100"><WifiOff className="mt-0.5 h-4 w-4 shrink-0" />{stream.error}</div>}
          </div>
        </div>
      </section>

      <VerdictOverlay verdict={visibleVerdict} score={stream.currentScore} reasons={stream.reasons} onClose={() => { if (stream.verdict === 'CRITICAL') setCriticalDismissed(true); else setSuspiciousDismissed(true) }} onEndCall={stream.stopSession} onAlert={() => void sendAlert()} alertSent={alertSent} />
      <PanicButton sessionId={stream.sessionId} onSent={() => setAlertSent(true)} />
    </div>
  )
}
