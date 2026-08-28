import { BellRing, BookOpen, Brain, Clock3, Languages, LayoutDashboard, LifeBuoy, Menu, Settings2, Shield } from 'lucide-react'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { CallMonitor } from './pages/CallMonitor'
import { EmergencyContacts } from './pages/EmergencyContacts'
import { Helplines } from './pages/Helplines'
import { History } from './pages/History'
import { Learn } from './pages/Learn'
import { Quiz } from './pages/Quiz'
import { ScamPractice } from './pages/ScamPractice'

interface NavigationItem {
  to: string
  labelKey: string
  icon: typeof LayoutDashboard
  desktop: boolean
}

const navigation: NavigationItem[] = [
  { to: '/call', labelKey: 'nav.call', icon: LayoutDashboard, desktop: true },
  { to: '/history', labelKey: 'nav.history', icon: Clock3, desktop: true },
  { to: '/learn', labelKey: 'nav.learn', icon: BookOpen, desktop: true },
  { to: '/helplines', labelKey: 'nav.helplines', icon: LifeBuoy, desktop: true },
  { to: '/quiz', labelKey: 'nav.quiz', icon: Brain, desktop: false },
]

function Brand() {
  const { t } = useTranslation()
  return (
    <Link to="/call" className="flex items-center gap-3" aria-label={t('app.name')}>
      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-sky-400/15 text-sky-300"><Shield className="h-5 w-5" aria-hidden="true" /></span>
      <span>
        <span className="block text-base font-bold tracking-tight text-white">{t('app.name')}</span>
        <span className="hidden text-[10px] font-semibold uppercase tracking-[0.19em] text-slate-500 sm:block">Armour safety layer</span>
      </span>
    </Link>
  )
}

function LanguageToggle() {
  const { i18n, t } = useTranslation()
  const current = i18n.language.toLowerCase().startsWith('hi') ? 'hi' : 'en'
  const toggleLanguage = () => {
    void i18n.changeLanguage(current === 'en' ? 'hi' : 'en')
  }
  return (
    <button type="button" onClick={toggleLanguage} title={t('common.language')} className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs font-bold text-slate-300 transition hover:border-sky-400/50 hover:text-white">
      <Languages className="h-4 w-4 text-sky-300" aria-hidden="true" />
      {current === 'en' ? 'EN' : 'HI'}
    </button>
  )
}

function TopBar() {
  const { t } = useTranslation()
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Brand />
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-2 rounded-full border border-risk-safe/20 bg-risk-safe/5 px-3 py-2 text-xs font-medium text-risk-safe md:flex"><span className="h-2 w-2 rounded-full bg-risk-safe" />Privacy mode on</span>
          <LanguageToggle />
          <Link to="/contacts" title={t('nav.contacts')} aria-label={t('nav.contacts')} className="rounded-xl border border-slate-700 bg-slate-900/60 p-2 text-slate-300 transition hover:border-sky-400/50 hover:text-white"><Settings2 className="h-5 w-5" aria-hidden="true" /></Link>
        </div>
      </div>
    </header>
  )
}

function BottomNavigation() {
  const { t } = useTranslation()
  const location = useLocation()
  const bottomItems = navigation.filter((item) => item.desktop).slice(0, 4)
  return (
    <nav aria-label="Primary navigation" className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-800/90 bg-slate-950/90 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl sm:hidden">
      <div className="mx-auto grid max-w-md grid-cols-4 gap-1">
        {bottomItems.map((item) => {
          const Icon = item.icon
          const active = location.pathname === item.to
          return <NavLink key={item.to} to={item.to} className={`flex flex-col items-center gap-1 rounded-xl px-2 py-2 text-[10px] font-semibold transition ${active ? 'bg-sky-400/10 text-sky-300' : 'text-slate-500 hover:text-slate-200'}`}><Icon className="h-5 w-5" aria-hidden="true" />{t(item.labelKey)}</NavLink>
        })}
      </div>
    </nav>
  )
}

function DesktopNavigation() {
  const { t } = useTranslation()
  return (
    <aside className="hidden w-52 shrink-0 lg:block">
      <nav className="sticky top-24 space-y-1" aria-label="Primary navigation">
        {navigation.filter((item) => item.desktop).map((item) => {
          const Icon = item.icon
          return <NavLink key={item.to} to={item.to} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${isActive ? 'bg-sky-400/10 text-sky-300' : 'text-slate-400 hover:bg-slate-900 hover:text-white'}`}><Icon className="h-4 w-4" aria-hidden="true" />{t(item.labelKey)}</NavLink>
        })}
        <div className="my-4 border-t border-slate-800" />
        <NavLink to="/practice" className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${isActive ? 'bg-yellow-400/10 text-yellow-300' : 'text-slate-400 hover:bg-slate-900 hover:text-white'}`}><BellRing className="h-4 w-4" aria-hidden="true" />{t('nav.practice')}</NavLink>
        <NavLink to="/contacts" className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold transition ${isActive ? 'bg-sky-400/10 text-sky-300' : 'text-slate-400 hover:bg-slate-900 hover:text-white'}`}><Menu className="h-4 w-4" aria-hidden="true" />{t('nav.contacts')}</NavLink>
      </nav>
    </aside>
  )
}

function AppShell() {
  const { i18n } = useTranslation()
  useEffect(() => {
    document.documentElement.lang = i18n.language.toLowerCase().startsWith('hi') ? 'hi' : 'en'
  }, [i18n.language])
  return (
    <div className="min-h-screen text-slate-100">
      <TopBar />
      <div className="mx-auto flex max-w-6xl gap-8 px-4 sm:px-6 lg:px-8">
        <DesktopNavigation />
        <main className="min-w-0 flex-1"><Routes><Route path="/" element={<Navigate to="/call" replace />} /><Route path="/call" element={<CallMonitor />} /><Route path="/history" element={<History />} /><Route path="/helplines" element={<Helplines />} /><Route path="/learn" element={<Learn />} /><Route path="/quiz" element={<Quiz />} /><Route path="/practice" element={<ScamPractice />} /><Route path="/contacts" element={<EmergencyContacts />} /></Routes></main>
      </div>
      <BottomNavigation />
    </div>
  )
}

export default function App() {
  return <BrowserRouter><AppShell /></BrowserRouter>
}
