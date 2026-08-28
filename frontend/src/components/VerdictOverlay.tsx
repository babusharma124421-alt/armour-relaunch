import { AlertTriangle, CheckCircle2, ExternalLink, PhoneCall, ShieldX, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Verdict } from '../lib/api'

interface VerdictOverlayProps {
  verdict: Verdict | null
  score: number
  reasons: string[]
  onClose: () => void
  onEndCall: () => void
  onAlert: () => void
  alertSent: boolean
}

function verdictLabel(verdict: Verdict, t: (key: string, options?: Record<string, unknown>) => string): string {
  if (verdict === 'CRITICAL') return t('verdict.critical')
  if (verdict === 'SUSPICIOUS') return t('verdict.suspicious')
  return t('verdict.safe')
}

export function VerdictOverlay({ verdict, score, reasons, onClose, onEndCall, onAlert, alertSent }: VerdictOverlayProps) {
  const { t } = useTranslation()
  const [secondsLeft, setSecondsLeft] = useState(3)

  useEffect(() => {
    if (verdict !== 'CRITICAL') {
      setSecondsLeft(0)
      return undefined
    }
    setSecondsLeft(3)
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => Math.max(0, current - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [verdict])

  if (!verdict) return null

  if (verdict === 'SAFE') {
    return (
      <div className="mt-5 flex items-center gap-3 rounded-2xl border border-risk-safe/20 bg-risk-safe/5 px-4 py-3 text-sm text-risk-safe">
        <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden="true" />
        {t('verdict.safe.message')}
      </div>
    )
  }

  if (verdict === 'SUSPICIOUS') {
    return (
      <div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl border border-risk-suspicious/30 bg-risk-suspicious/10 px-4 py-3 text-sm text-yellow-100">
        <AlertTriangle className="h-5 w-5 shrink-0 text-risk-suspicious" aria-hidden="true" />
        <span className="flex-1">{t('verdict.suspicious.message')}</span>
        <span className="rounded-full bg-risk-suspicious/15 px-3 py-1 font-semibold text-risk-suspicious">{Math.round(score)}/100</span>
        <button type="button" onClick={onAlert} disabled={alertSent} className="secondary-button border-yellow-500/30 px-3 py-2 text-xs text-yellow-100">
          {alertSent ? t('action.alert_sent') : t('action.alert_contacts')}
        </button>
        <button type="button" onClick={onClose} aria-label={t('action.close')} className="rounded-xl p-2 text-yellow-100/70 transition hover:bg-yellow-200/10 hover:text-yellow-100">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    )
  }

  const locked = secondsLeft > 0
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-red-950/80 p-4 backdrop-blur-md sm:items-center">
      <div role="alertdialog" aria-modal="true" aria-labelledby="critical-verdict-title" className="w-full max-w-xl overflow-hidden rounded-3xl border border-red-300/30 bg-slate-950 shadow-2xl shadow-red-950/60">
        <div className="border-b border-red-400/20 bg-red-500/10 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-red-500/15 p-3 text-red-400"><ShieldX className="h-7 w-7" aria-hidden="true" /></div>
              <div>
                <p className="eyebrow text-red-300">{t('verdict.critical')}</p>
                <h2 id="critical-verdict-title" className="mt-1 text-2xl font-bold text-white">{t('verdict.critical.message')}</h2>
              </div>
            </div>
            <button type="button" onClick={onClose} disabled={locked} aria-label={t('action.close')} className="rounded-full p-2 text-slate-400 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-30">
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
          <p className="mt-5 text-4xl font-semibold text-red-300">{Math.round(score)}<span className="text-lg text-red-200/60">/100</span></p>
          {locked && <p className="mt-2 text-sm text-red-200/70">{t('verdict.overlay_lock', { seconds: secondsLeft })}</p>}
        </div>
        <div className="space-y-5 px-6 py-5">
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{t('call.reason_heading')}</p>
            <ul className="space-y-2">
              {reasons.slice(0, 2).map((reason) => <li key={reason} className="flex gap-2 text-sm text-slate-200"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-red-400" />{reason}</li>)}
            </ul>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <button type="button" onClick={onEndCall} className="primary-button bg-red-500 text-white hover:bg-red-400"><PhoneCall className="h-4 w-4" />{t('action.end_call')}</button>
            <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer" className="secondary-button"><ExternalLink className="h-4 w-4" />{t('action.verify')}</a>
            <a className={`secondary-button ${locked ? 'pointer-events-none opacity-50' : ''}`} aria-disabled={locked} href="tel:1930" onClick={(event) => { if (locked) { event.preventDefault(); return } onClose() }}><PhoneCall className="h-4 w-4" />{t('action.report_1930')}</a>
            <button type="button" onClick={onAlert} disabled={alertSent || locked} className="secondary-button border-red-400/40 text-red-200 disabled:opacity-50"><ShieldX className="h-4 w-4" />{alertSent ? t('action.alert_sent') : t('action.alert_contacts')}</button>
          </div>
          <p className="text-center text-xs text-slate-500">{verdictLabel(verdict, t)} · {t('verdict.score', { score: Math.round(score) })}</p>
        </div>
      </div>
    </div>
  )
}
