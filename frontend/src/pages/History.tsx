import { AlertCircle, BellRing, ChevronDown, ChevronUp, Clock3, History as HistoryIcon, LineChart as LineChartIcon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchJson, type SessionHistory, type SessionSummary, type Verdict } from '../lib/api'

interface SessionsResponse {
  items: SessionSummary[]
  limit: number
  offset: number
  has_more: boolean
}

interface ChartPoint {
  segment: number
  score: number
}

const verdictClasses: Record<Verdict, string> = {
  SAFE: 'border-risk-safe/30 bg-risk-safe/10 text-risk-safe',
  SUSPICIOUS: 'border-risk-suspicious/30 bg-risk-suspicious/10 text-risk-suspicious',
  CRITICAL: 'border-risk-critical/30 bg-risk-critical/10 text-risk-critical',
}

export function History() {
  const { t, i18n } = useTranslation()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [histories, setHistories] = useState<Record<string, SessionHistory>>({})

  const loadSessions = useCallback(async (nextOffset: number, append: boolean) => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetchJson<SessionsResponse>(`/sessions/all?limit=10&offset=${nextOffset}`)
      setSessions((current) => append ? [...current, ...response.items] : response.items)
      setOffset(nextOffset + response.items.length)
      setHasMore(response.has_more)
    } catch {
      setError(t('history.load_error'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { void loadSessions(0, false) }, [loadSessions])

  const toggleSession = async (sessionId: string) => {
    if (expanded === sessionId) {
      setExpanded(null)
      return
    }
    setExpanded(sessionId)
    if (!histories[sessionId]) {
      try {
        const response = await fetchJson<SessionHistory>(`/session/${sessionId}/history`)
        setHistories((current) => ({ ...current, [sessionId]: response }))
      } catch {
        setError(t('history.load_error'))
      }
    }
  }

  const formatDate = (date: string) => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date))

  return (
    <div className="page-shell">
      <div className="mb-7"><p className="eyebrow">Private evidence trail</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('history.title')}</h1><p className="mt-2 text-sm leading-6 text-slate-400">{t('history.subtitle')}</p></div>
      {error && <div className="mb-5 flex items-center gap-3 rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100"><AlertCircle className="h-4 w-4" />{error}</div>}
      {!loading && sessions.length === 0 ? <div className="glass-panel flex min-h-80 flex-col items-center justify-center rounded-3xl px-6 text-center"><div className="rounded-2xl bg-sky-400/10 p-4 text-sky-300"><HistoryIcon className="h-8 w-8" /></div><h2 className="mt-5 text-xl font-semibold text-white">{t('history.empty')}</h2><p className="mt-2 max-w-sm text-sm leading-6 text-slate-400">Start a protected call to see score history here.</p></div> : <div className="space-y-3">{sessions.map((session) => {
        const history = histories[session.id]
        const verdict = session.verdict
        const points: ChartPoint[] = history?.events.map((event, index) => ({ segment: index + 1, score: Math.round(event.final_score) })) ?? []
        return <article key={session.id} className="glass-panel overflow-hidden rounded-2xl"><button type="button" className="flex w-full items-center gap-4 p-4 text-left sm:p-5" onClick={() => void toggleSession(session.id)}><div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${verdict ? verdictClasses[verdict] : 'bg-slate-800 text-slate-400'}`}><Clock3 className="h-5 w-5" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold text-white">{formatDate(session.created_at)}</span><span className="rounded-full border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{session.is_practice ? t('history.practice') : t('history.live')}</span></div><p className="mt-1 text-xs text-slate-500">{session.language.toUpperCase()} · {session.alert_sent ? t('history.alert_sent') : t('history.no_alert')}</p></div><div className="text-right"><p className={`text-lg font-bold ${verdict ? verdictClasses[verdict].split(' ').at(-1) : 'text-slate-300'}`}>{session.final_score === null ? '—' : Math.round(session.final_score)}</p><p className="text-[10px] uppercase tracking-wider text-slate-500">{t('history.score')}</p></div>{expanded === session.id ? <ChevronUp className="h-5 w-5 text-slate-500" /> : <ChevronDown className="h-5 w-5 text-slate-500" />}</button>{expanded === session.id && <div className="border-t border-slate-800/80 p-4 sm:p-5"><div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200"><LineChartIcon className="h-4 w-4 text-sky-300" />{history ? t('history.events', { count: history.events.length }) : t('common.loading')}</div>{points.length > 0 ? <div className="h-56 w-full"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}><CartesianGrid stroke="#1e293b" strokeDasharray="3 3" /><XAxis dataKey="segment" stroke="#64748b" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} stroke="#64748b" tick={{ fontSize: 11 }} /><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12 }} labelFormatter={(label) => `Segment ${label}`} /><Line type="monotone" dataKey="score" stroke="#38bdf8" strokeWidth={3} dot={{ fill: '#38bdf8', r: 3 }} /></LineChart></ResponsiveContainer></div> : <p className="text-sm text-slate-500">{history ? t('history.empty') : t('common.loading')}</p>}</div>}</article>
      })}</div>}
      {loading && <div className="py-8 text-center text-sm text-slate-500">{t('common.loading')}</div>}
      {!loading && hasMore && <button type="button" onClick={() => void loadSessions(offset, true)} className="secondary-button mx-auto mt-6"><BellRing className="h-4 w-4" />{t('action.load_more')}</button>}
    </div>
  )
}
