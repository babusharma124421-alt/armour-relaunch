import { Check, Copy, ExternalLink, PhoneCall } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Helpline } from '../lib/api'

interface HelplineCardProps {
  helpline: Helpline
}

function isPhoneNumber(value: string): boolean {
  return /^[+\d][\d\s()-]+$/.test(value)
}

export function HelplineCard({ helpline }: HelplineCardProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const dialable = isPhoneNumber(helpline.number)

  const copyNumber = async () => {
    try {
      await navigator.clipboard.writeText(helpline.number)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <article className="glass-panel flex h-full flex-col rounded-2xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">{t(`helplines.category_${helpline.category}`, { defaultValue: t('helplines.category_unknown') })}</p>
          <h3 className="mt-2 text-lg font-semibold text-white">{helpline.name}</h3>
        </div>
        <div className="rounded-xl bg-sky-500/10 p-2 text-sky-300"><PhoneCall className="h-5 w-5" aria-hidden="true" /></div>
      </div>
      <p className="mt-4 text-2xl font-semibold tracking-tight text-sky-200">{helpline.number}</p>
      <p className="mt-3 flex-1 text-sm leading-6 text-slate-400">{helpline.description}</p>
      <p className="mt-4 text-xs font-medium text-slate-500">{helpline.available_hours}</p>
      <div className="mt-5 grid grid-cols-2 gap-2">
        {dialable ? <a href={`tel:${helpline.number.replace(/[^\d+]/g, '')}`} className="primary-button px-3 py-2 text-sm"><PhoneCall className="h-4 w-4" />{t('helplines.call')}</a> : <a href={`https://${helpline.number}`} target="_blank" rel="noreferrer" className="primary-button px-3 py-2 text-sm"><ExternalLink className="h-4 w-4" />{t('helplines.call')}</a>}
        <button type="button" onClick={() => void copyNumber()} className="secondary-button px-3 py-2 text-sm">{copied ? <Check className="h-4 w-4 text-risk-safe" /> : <Copy className="h-4 w-4" />}{copied ? t('action.copied') : t('helplines.copy')}</button>
      </div>
    </article>
  )
}
