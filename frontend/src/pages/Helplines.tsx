import { AlertCircle, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { HelplineCard } from '../components/HelplineCard'
import { fetchJson, type Helpline } from '../lib/api'

export function Helplines() {
  const { t } = useTranslation()
  const [helplines, setHelplines] = useState<Helpline[]>([])
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchJson<Helpline[]>('/helplines')
      .then(setHelplines)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  const categories = useMemo(() => ['all', ...Array.from(new Set(helplines.map((helpline) => helpline.category)))], [helplines])
  const visible = useMemo(() => helplines.filter((helpline) => {
    const categoryMatches = category === 'all' || helpline.category === category
    const query = search.toLowerCase().trim()
    return categoryMatches && (!query || `${helpline.name} ${helpline.number}`.toLowerCase().includes(query))
  }), [category, helplines, search])
  const grouped = useMemo(() => visible.reduce<Record<string, Helpline[]>>((groups, helpline) => {
    const key = helpline.category
    groups[key] = groups[key] ? [...groups[key], helpline] : [helpline]
    return groups
  }, {}), [visible])

  return (
    <div className="page-shell">
      <div className="mb-7"><p className="eyebrow">Trusted response channels</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('helplines.title')}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{t('helplines.subtitle')}</p></div>
      {error && <div className="mb-5 flex items-center gap-3 rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100"><AlertCircle className="h-4 w-4" />{t('common.error')}</div>}
      <div className="glass-panel rounded-2xl p-4"><div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('helplines.search')} className="w-full rounded-xl border border-slate-700 bg-slate-950/70 py-3 pl-10 pr-4 text-sm text-white placeholder:text-slate-600" /></div><div className="mt-4 flex gap-2 overflow-x-auto pb-1">{categories.map((item) => <button key={item} type="button" onClick={() => setCategory(item)} className={`whitespace-nowrap rounded-full border px-3 py-2 text-xs font-semibold capitalize transition ${category === item ? 'border-sky-400/40 bg-sky-400/10 text-sky-300' : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:text-white'}`}>{item === 'all' ? t('helplines.all') : item.replace(/_/g, ' ')}</button>)}</div></div>
      {loading ? <p className="py-10 text-center text-sm text-slate-500">{t('common.loading')}</p> : visible.length === 0 ? <div className="py-12 text-center text-sm text-slate-500">{t('helplines.empty')}</div> : <div className="mt-6 space-y-8">{Object.entries(grouped).map(([group, items]) => <section key={group}><h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{group.replace(/_/g, ' ')}</h2><div className="grid gap-4 md:grid-cols-2">{items.map((helpline) => <HelplineCard key={`${helpline.name}-${helpline.number}`} helpline={helpline} />)}</div></section>)}</div>}
    </div>
  )
}
