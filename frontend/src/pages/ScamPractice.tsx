import { AlertTriangle, ArrowRight, CheckCircle2, Play, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { RiskGauge } from '../components/RiskGauge'
import { useCallStream } from '../hooks/useCallStream'
import type { RiskPayload, Verdict } from '../lib/api'
import scripts from '../content/practice_scripts.json'

interface PracticeScript {
  id: string
  risk: 'benign' | 'medium' | 'critical'
  language: 'en' | 'hi'
  titleKey: string
  text: string
}

const allScripts = scripts as PracticeScript[]

const patternLessons: Record<string, string> = {
  authority_claim_en: 'authority',
  authority_claim_hi: 'authority',
  arrest_threat_en: 'urgency',
  arrest_threat_hi: 'urgency',
  secrecy_request_en: 'secrecy',
  secrecy_request_hi: 'secrecy',
  money_transfer_en: 'upi',
  money_transfer_hi: 'upi',
  aadhaar_crime_link_en: 'authority',
  aadhaar_crime_link_hi: 'authority',
  video_call_trap_en: 'digital_arrest',
  video_call_trap_hi: 'digital_arrest',
  sim_deactivation_en: 'urgency',
  sim_deactivation_hi: 'urgency',
}

function practicePayloads(script: PracticeScript): RiskPayload[] {
  const score = script.risk === 'critical' ? 91 : script.risk === 'medium' ? 47 : 10
  const patterns = script.risk === 'critical'
    ? ['authority_claim_en', 'aadhaar_crime_link_en', 'arrest_threat_en', 'secrecy_request_en', 'money_transfer_en']
    : script.risk === 'medium' ? ['sim_deactivation_en', 'urgency_deadline_en'] : []
  const language = script.language
  return [0.35, 0.62, 0.82, 1].map((progress) => {
    const finalScore = Math.round(score * progress)
    const verdict: Verdict = finalScore > 70 ? 'CRITICAL' : finalScore >= 30 ? 'SUSPICIOUS' : 'SAFE'
    return {
      voice_score: script.risk === 'critical' ? 40 : 10,
      script_score: finalScore,
      intent_score: finalScore,
      caller_score: 0,
      behavior_score: Math.round(finalScore * 0.85),
      final_score: finalScore,
      verdict,
      reasons: patterns.length > 0 ? ['This fictional call contains recognizable social-engineering signals.'] : ['No strong scam indicators were detected in this practice script.'],
      matched_patterns: patterns,
      transcript_snippet: script.text.slice(-280),
      detected_language: language,
      breakdown: { voice: script.risk === 'critical' ? 40 : 10, intent: finalScore, caller: 0, behavior: Math.round(finalScore * 0.85) },
    }
  })
}

export function ScamPractice() {
  const { t, i18n } = useTranslation()
  const language = i18n.language.toLowerCase().startsWith('hi') ? 'hi' : 'en'
  const localizedScripts = useMemo(() => allScripts.filter((script) => script.language === language), [language])
  const [selectedId, setSelectedId] = useState(localizedScripts[0]?.id ?? 'benign_en')
  const [started, setStarted] = useState(false)
  const selected = localizedScripts.find((script) => script.id === selectedId) ?? localizedScripts[0] ?? allScripts[0]
  const payloads = useMemo(() => practicePayloads(selected), [selected])
  const stream = useCallStream({ isPractice: true, practiceScript: selected.text, practicePayloads: payloads })
  const running = stream.status === 'requesting_permission' || stream.status === 'listening' || stream.status === 'analyzing'
  const complete = started && !running && stream.currentScore > 0

  useEffect(() => {
    if (!localizedScripts.some((script) => script.id === selectedId)) setSelectedId(localizedScripts[0]?.id ?? 'benign_en')
  }, [localizedScripts, selectedId])

  const start = () => {
    setStarted(true)
    stream.startSession()
  }

  return (
    <div className="page-shell">
      <div className="sticky top-[4.5rem] z-20 mb-6 flex items-center gap-3 rounded-2xl border border-yellow-400/40 bg-yellow-400/10 px-4 py-3 text-sm font-bold text-yellow-100 shadow-lg shadow-slate-950/20"><AlertTriangle className="h-5 w-5 shrink-0 text-yellow-300" />{t('practice.banner')}</div>
      <div className="mb-7"><p className="eyebrow text-yellow-300">Safe rehearsal room</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('practice.title')}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{t('practice.subtitle')}</p></div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(320px,1.1fr)]">
        <section className="glass-panel rounded-3xl p-5 sm:p-7"><label htmlFor="practice-script" className="eyebrow">{t('practice.choose')}</label><select id="practice-script" value={selected.id} onChange={(event) => { setSelectedId(event.target.value); setStarted(false); stream.stopSession() }} className="mt-3 w-full rounded-xl border border-slate-700 bg-slate-950/80 px-4 py-3 text-sm font-semibold text-white"><option value={selected.id}>{t(selected.titleKey)}</option>{localizedScripts.filter((script) => script.id !== selected.id).map((script) => <option key={script.id} value={script.id}>{t(script.titleKey)}</option>)}</select><div className="mt-5 rounded-2xl border border-yellow-400/20 bg-yellow-400/5 p-4"><p className="text-xs font-semibold uppercase tracking-wider text-yellow-200">{t(selected.titleKey)}</p><p className="mt-3 text-sm leading-7 text-slate-300">{selected.text}</p></div><p className="mt-4 text-xs leading-5 text-slate-500">{t('practice.note')}</p><button type="button" onClick={running ? stream.stopSession : start} className={`mt-6 w-full rounded-xl px-4 py-3 font-bold transition ${running ? 'border border-red-400/40 bg-red-500/10 text-red-200' : 'bg-yellow-400 text-slate-950 hover:bg-yellow-300'}`}>{running ? <span className="inline-flex items-center gap-2"><RotateCcw className="h-4 w-4" />{t('call.stop')}</span> : started && complete ? <span className="inline-flex items-center gap-2"><Play className="h-4 w-4" />{t('practice.restart')}</span> : <span className="inline-flex items-center gap-2"><Play className="h-4 w-4" />{t('practice.start')}</span>}</button></section>
        <section className="glass-panel rounded-3xl p-5 sm:p-7"><div className="flex items-center justify-between gap-3"><div><p className="eyebrow">{running ? t('practice.running') : complete ? t('practice.complete') : t('call.idle')}</p><h2 className="mt-2 text-xl font-semibold text-white">{t('call.score_label')}</h2></div><span className={`rounded-full px-3 py-1 text-xs font-bold ${stream.verdict === 'CRITICAL' ? 'bg-risk-critical/15 text-risk-critical' : stream.verdict === 'SUSPICIOUS' ? 'bg-risk-suspicious/15 text-risk-suspicious' : 'bg-risk-safe/15 text-risk-safe'}`}>{stream.verdict ? t(`verdict.${stream.verdict.toLowerCase()}`) : '—'}</span></div><div className="mt-6 flex justify-center"><RiskGauge score={stream.currentScore} verdict={stream.verdict} size={260} /></div>{complete && <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/50 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4 text-risk-safe" />{t('practice.triggered')}</div>{stream.matchedPatterns.length === 0 ? <p className="mt-3 text-sm text-slate-500">{t('practice.triggered_empty')}</p> : <ul className="mt-3 space-y-2">{stream.matchedPatterns.map((pattern) => <li key={pattern} className="flex items-center justify-between gap-3 rounded-xl bg-slate-900 px-3 py-2 text-sm text-slate-300"><span>{pattern.replace(/_/g, ' ')}</span>{patternLessons[pattern] && <Link to={`/learn#${patternLessons[pattern]}`} className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-sky-300 hover:text-sky-200">{t('practice.view_lesson')}<ArrowRight className="h-3 w-3" /></Link>}</li>)}</ul>}</div>}</section>
      </div>
    </div>
  )
}
