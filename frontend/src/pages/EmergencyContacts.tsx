import { AlertCircle, Plus, Shield, Trash2, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchJson, getDeviceId, type EmergencyContact } from '../lib/api'

interface ContactForm {
  name: string
  phone: string
  relationship: string
}

const emptyForm: ContactForm = { name: '', phone: '', relationship: '' }

export function EmergencyContacts() {
  const { t } = useTranslation()
  const [contacts, setContacts] = useState<EmergencyContact[]>([])
  const [form, setForm] = useState<ContactForm>(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const deviceId = getDeviceId()

  const loadContacts = async () => {
    setLoading(true)
    try {
      const data = await fetchJson<EmergencyContact[]>(`/contacts?user_session_owner_id=${encodeURIComponent(deviceId)}`)
      setContacts(data)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadContacts() }, [])

  const addContact = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setMessage(null)
    if (!form.name.trim() || form.phone.replace(/\D/g, '').length < 7) {
      setMessage(t('contacts.validation'))
      return
    }
    setSaving(true)
    try {
      const contact = await fetchJson<EmergencyContact>('/contacts', { method: 'POST', body: JSON.stringify({ user_session_owner_id: deviceId, ...form }) })
      setContacts((current) => [...current, contact])
      setForm(emptyForm)
      setMessage(null)
    } catch {
      setMessage(t('contacts.save_error'))
    } finally {
      setSaving(false)
    }
  }

  const removeContact = async (id: string) => {
    try {
      await fetchJson<{ success: boolean }>(`/contacts/${id}`, { method: 'DELETE' })
      setContacts((current) => current.filter((contact) => contact.id !== id))
    } catch {
      setMessage(t('contacts.remove_error'))
    }
  }

  return (
    <div className="page-shell">
      <div className="mb-7"><p className="eyebrow">Your safety circle</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">{t('contacts.title')}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{t('contacts.subtitle')}</p></div>
      {error && <div className="mb-5 flex items-center gap-3 rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100"><AlertCircle className="h-4 w-4" />{t('contacts.load_error')}</div>}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(320px,1.15fr)]">
        <section className="glass-panel rounded-3xl p-5 sm:p-7"><div className="flex items-center justify-between gap-3"><div><p className="eyebrow">{t('contacts.add')}</p><h2 className="mt-2 text-xl font-semibold text-white">{t('contacts.limit', { count: contacts.length })}</h2></div><div className="rounded-2xl bg-sky-400/10 p-3 text-sky-300"><Shield className="h-5 w-5" /></div></div><form onSubmit={(event) => void addContact(event)} className="mt-7 space-y-4"><label className="block"><span className="text-sm font-medium text-slate-300">{t('contacts.name')}</span><input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white placeholder:text-slate-600" /></label><label className="block"><span className="text-sm font-medium text-slate-300">{t('contacts.phone')}</span><input required type="tel" value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white placeholder:text-slate-600" /></label><label className="block"><span className="text-sm font-medium text-slate-300">{t('contacts.relationship')}</span><input value={form.relationship} placeholder={t('contacts.relationship_placeholder')} onChange={(event) => setForm((current) => ({ ...current, relationship: event.target.value }))} className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-white placeholder:text-slate-600" /></label>{message && <p className="text-sm text-red-200">{message}</p>}<button type="submit" disabled={saving || contacts.length >= 5} className="primary-button w-full"><Plus className="h-4 w-4" />{saving ? t('common.loading') : t('contacts.save')}</button></form></section>
        <section className="space-y-3">{loading ? <div className="glass-panel rounded-3xl p-8 text-center text-sm text-slate-500">{t('common.loading')}</div> : contacts.length === 0 ? <div className="glass-panel flex min-h-64 flex-col items-center justify-center rounded-3xl p-8 text-center"><UserRound className="h-9 w-9 text-slate-600" /><p className="mt-4 text-sm text-slate-500">{t('contacts.empty')}</p></div> : contacts.map((contact) => <article key={contact.id} className="glass-panel flex items-center gap-4 rounded-2xl p-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-sky-400/10 text-sky-300"><UserRound className="h-5 w-5" /></div><div className="min-w-0 flex-1"><h3 className="font-semibold text-white">{contact.name}</h3><p className="mt-1 text-sm text-slate-400">{contact.phone}</p>{contact.relationship && <p className="mt-1 text-xs text-slate-500">{contact.relationship}</p>}</div><button type="button" onClick={() => void removeContact(contact.id)} aria-label={`${t('contacts.remove')} ${contact.name}`} className="rounded-xl p-2 text-slate-500 transition hover:bg-red-500/10 hover:text-red-300"><Trash2 className="h-4 w-4" /></button></article>)}</section>
      </div>
    </div>
  )
}
