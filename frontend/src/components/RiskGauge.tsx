import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Verdict } from '../lib/api'

interface RiskGaugeProps {
  score: number
  verdict: Verdict | null
  size?: number
}

const verdictStyles: Record<'SAFE' | 'SUSPICIOUS' | 'CRITICAL' | 'default', { stroke: string; text: string; icon: typeof ShieldCheck }> = {
  SAFE: { stroke: '#22c55e', text: 'text-risk-safe', icon: ShieldCheck },
  SUSPICIOUS: { stroke: '#eab308', text: 'text-risk-suspicious', icon: ShieldAlert },
  CRITICAL: { stroke: '#ef4444', text: 'text-risk-critical', icon: ShieldX },
  default: { stroke: '#38bdf8', text: 'text-sky-300', icon: ShieldCheck },
}

export function RiskGauge({ score, verdict, size = 320 }: RiskGaugeProps) {
  const { t } = useTranslation()
  const safeScore = Math.max(0, Math.min(100, score))
  const style = verdictStyles[verdict ?? 'default']
  const Icon = style.icon
  const strokeWidth = 13
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (safeScore / 100) * circumference

  return (
    <div className="relative mx-auto aspect-square" style={{ width: size, maxWidth: '100%' }} aria-label={t('call.score_aria', { score: Math.round(safeScore) })}>
      <svg className="h-full w-full -rotate-90" viewBox={`0 0 ${size} ${size}`} role="img">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#1e293b" strokeWidth={strokeWidth} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={style.stroke}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
        <Icon className={`h-6 w-6 ${style.text}`} aria-hidden="true" />
        <span className={`text-6xl font-semibold tracking-tight ${style.text}`}>{Math.round(safeScore)}</span>
        <span className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">{t('call.score_label')}</span>
      </div>
    </div>
  )
}
