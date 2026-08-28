import { Siren } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchJson, getDeviceId } from '../lib/api'

interface PanicButtonProps {
  sessionId: string | null
  onSent?: () => void
}

interface PanicResponse {
  notified_count: number
  success: boolean
}

export function PanicButton({ sessionId, onSent }: PanicButtonProps) {
  const { t } = useTranslation()
  const [sending, setSending] = useState(false)

  const handlePanic = async () => {
    if (!sessionId) {
      window.alert(t('panic.none'))
      return
    }
    if (!window.confirm(t('panic.confirm'))) return
    setSending(true)
    try {
      const response = await fetchJson<PanicResponse>('/panic', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, user_session_owner_id: getDeviceId() }),
      })
      if (response.success) {
        window.alert(t('panic.sent'))
        onSent?.()
      } else {
        window.alert(t('panic.failed'))
      }
    } catch {
      window.alert(t('panic.failed'))
    } finally {
      setSending(false)
    }
  }

  return (
    <button type="button" onClick={() => void handlePanic()} disabled={sending} aria-label={t('panic.title')} className="fixed bottom-24 right-5 z-40 inline-flex items-center gap-2 rounded-full border border-red-300/40 bg-red-500 px-4 py-3 text-sm font-bold text-white shadow-xl shadow-red-950/40 transition hover:bg-red-400 disabled:cursor-wait disabled:opacity-70 sm:bottom-8 sm:right-8">
      <Siren className="h-4 w-4" aria-hidden="true" />
      <span>{sending ? '…' : t('panic.button')}</span>
    </button>
  )
}
