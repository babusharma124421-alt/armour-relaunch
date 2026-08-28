import { BadgeInfo, Banknote, Building2, Camera, Clock3, Eye, HeartHandshake, KeyRound, LockKeyhole, MessageCircleWarning, ShieldCheck, Smartphone, UserRound } from 'lucide-react'

export interface AwarenessItem {
  id: string
  title: string
  body: string
  icon: string
  category: string
}

interface AwarenessCardProps {
  item: AwarenessItem
}

const icons: Record<string, typeof ShieldCheck> = {
  authority: Building2,
  urgency: Clock3,
  secrecy: LockKeyhole,
  otp: KeyRound,
  verify: ShieldCheck,
  remote_access: Smartphone,
  digital_arrest: Camera,
  upi: Banknote,
  banking: Building2,
  emotional: HeartHandshake,
  elderly: UserRound,
  official_channels: BadgeInfo,
  privacy: Eye,
  warning: MessageCircleWarning,
}

export function AwarenessCard({ item }: AwarenessCardProps) {
  const Icon = icons[item.icon] ?? ShieldCheck
  return (
    <article className="glass-panel min-h-[270px] rounded-3xl p-6 sm:p-8">
      <div className="flex items-center justify-between gap-4">
        <div className="rounded-2xl bg-sky-500/10 p-3 text-sky-300"><Icon className="h-7 w-7" aria-hidden="true" /></div>
        <span className="rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-400">{item.category}</span>
      </div>
      <h2 className="mt-7 text-2xl font-semibold text-white">{item.title}</h2>
      <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">{item.body}</p>
    </article>
  )
}
