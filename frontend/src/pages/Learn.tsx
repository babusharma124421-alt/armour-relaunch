import { ArrowLeft, ArrowRight, BookOpenCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AwarenessCard, type AwarenessItem } from '../components/AwarenessCard'
import awarenessEn from '../content/awareness_en.json'
import awarenessHi from '../content/awareness_hi.json'

export function Learn() {
  const { t, i18n } = useTranslation()
  const items = (i18n.language.toLowerCase().startsWith('hi') ? awarenessHi : awarenessEn) as AwarenessItem[]
  const [current, setCurrent] = useState(0)

  useEffect(() => setCurrent(0), [i18n.language])
  const item = items[current]

  return (
    <div className="page-shell">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">{t('learn.eyebrow')}</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('learn.title')}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{t('learn.subtitle')}</p></div><Link to="/quiz" className="secondary-button"><BookOpenCheck className="h-4 w-4 text-sky-300" />{t('learn.open_quiz')}</Link></div>
      <div className="mx-auto max-w-3xl"><AwarenessCard item={item} /><div className="mt-5 flex items-center justify-between gap-4"><button type="button" disabled={current === 0} onClick={() => setCurrent((value) => Math.max(0, value - 1))} className="secondary-button disabled:opacity-30"><ArrowLeft className="h-4 w-4" />{t('action.back')}</button><div className="text-center"><p className="text-sm font-semibold text-slate-300">{t('learn.progress', { current: current + 1, total: items.length })}</p><div className="mt-2 flex justify-center gap-1">{items.map((entry, index) => <button key={entry.id} type="button" aria-label={`${index + 1}`} onClick={() => setCurrent(index)} className={`h-1.5 rounded-full transition-all ${index === current ? 'w-8 bg-sky-400' : 'w-2 bg-slate-700'}`} />)}</div></div><button type="button" disabled={current === items.length - 1} onClick={() => setCurrent((value) => Math.min(items.length - 1, value + 1))} className="secondary-button disabled:opacity-30">{t('action.next')}<ArrowRight className="h-4 w-4" /></button></div></div>
    </div>
  )
}
