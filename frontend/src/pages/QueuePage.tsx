import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { pl } from 'date-fns/locale'
import { useThreads } from '@/hooks/useThreads'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { sendDemoMessage } from '@/lib/api'
import type { Status, Priority, Category, Thread } from '@/lib/types'

const PRIORITY_CLASS: Record<Priority, string> = {
  urgent: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-700',
}

const PRIORITY_LABEL: Record<Priority, string> = {
  urgent: 'Pilny',
  high: 'Wysoki',
  medium: 'Średni',
  low: 'Niski',
}

const STATUS_CLASS: Record<Status, string> = {
  new: 'bg-blue-100 text-blue-800',
  pending_review: 'bg-amber-100 text-amber-800',
  replied: 'bg-green-100 text-green-800',
  resolved: 'bg-gray-100 text-gray-600',
  escalated: 'bg-red-100 text-red-800',
}

const STATUS_LABEL: Record<Status, string> = {
  new: 'Nowy',
  pending_review: 'Do sprawdzenia',
  replied: 'Odpowiedziano',
  resolved: 'Zamknięty',
  escalated: 'Eskalowany',
}

const CATEGORY_LABEL: Record<string, string> = {
  maintenance: 'Usterka',
  payment: 'Płatność',
  noise_complaint: 'Hałas',
  lease: 'Najem',
  general: 'Ogólne',
  supplier: 'Dostawca',
  other: 'Inne',
}

function preview(thread: Thread): string {
  return thread.preview ?? '—'
}

function sender(thread: Thread): string {
  return thread.sender_ref ?? '—'
}

export default function QueuePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status | ''>('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [category, setCategory] = useState<Category | ''>('')

  // Demo message form state
  const [showForm, setShowForm] = useState(false)
  const [channel, setChannel] = useState<'email' | 'sms'>('email')
  const [from, setFrom] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  function resetForm() {
    setChannel('email')
    setFrom('')
    setSubject('')
    setBody('')
    setFormError(null)
  }

  async function handleSubmit() {
    if (!from.trim() || !body.trim()) {
      setFormError('Pola "Od" i "Treść" są wymagane.')
      return
    }
    setSubmitting(true)
    setFormError(null)
    try {
      const payload =
        channel === 'email'
          ? { channel: 'email' as const, from: from.trim(), subject: subject.trim(), body: body.trim() }
          : { channel: 'sms' as const, from: from.trim(), body: body.trim() }
      await sendDemoMessage(payload)
      await queryClient.invalidateQueries({ queryKey: ['threads'] })
      setShowForm(false)
      resetForm()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Nieznany błąd.')
    } finally {
      setSubmitting(false)
    }
  }

  const { data, isLoading, isError } = useThreads({
    status: status || undefined,
    priority: priority || undefined,
    category: category || undefined,
  })

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Kolejka wiadomości</h1>
        <Button variant="outline" size="sm" onClick={() => { resetForm(); setShowForm(true) }}>
          + Dodaj wiadomość
        </Button>
      </div>

      {/* Demo message modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-background rounded-lg border shadow-lg w-full max-w-md p-6 space-y-4">
            <h2 className="text-base font-semibold">Wyślij testową wiadomość</h2>

            {/* Channel toggle */}
            <div className="flex gap-2">
              <button
                className={`px-3 py-1 rounded text-sm border ${channel === 'email' ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                onClick={() => setChannel('email')}
              >
                Email
              </button>
              <button
                className={`px-3 py-1 rounded text-sm border ${channel === 'sms' ? 'bg-primary text-primary-foreground' : 'bg-background'}`}
                onClick={() => setChannel('sms')}
              >
                SMS
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">
                  Od {channel === 'email' ? '(adres e-mail)' : '(numer telefonu)'}
                </label>
                <input
                  className="w-full border rounded px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                  placeholder={channel === 'email' ? 'mieszkaniec@example.com' : '+48600000000'}
                />
              </div>

              {channel === 'email' && (
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Temat</label>
                  <input
                    className="w-full border rounded px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="np. Usterka w mieszkaniu"
                  />
                </div>
              )}

              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Treść</label>
                <Textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Treść wiadomości…"
                  rows={4}
                />
              </div>
            </div>

            {formError && <p className="text-xs text-red-600">{formError}</p>}

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" size="sm" onClick={() => { setShowForm(false); resetForm() }} disabled={submitting}>
                Anuluj
              </Button>
              <Button size="sm" onClick={handleSubmit} disabled={submitting}>
                {submitting ? 'Wysyłanie…' : 'Wyślij'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Filtry */}
      <div className="flex gap-3 mb-4">
        <Select value={status} onValueChange={(v) => setStatus(v as Status | '')}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Wszystkie statusy" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Wszystkie statusy</SelectItem>
            <SelectItem value="new">Nowy</SelectItem>
            <SelectItem value="pending_review">Do sprawdzenia</SelectItem>
            <SelectItem value="replied">Odpowiedziano</SelectItem>
            <SelectItem value="resolved">Zamknięty</SelectItem>
            <SelectItem value="escalated">Eskalowany</SelectItem>
          </SelectContent>
        </Select>

        <Select value={priority} onValueChange={(v) => setPriority(v as Priority | '')}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Wszystkie priorytety" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Wszystkie priorytety</SelectItem>
            <SelectItem value="urgent">Pilny</SelectItem>
            <SelectItem value="high">Wysoki</SelectItem>
            <SelectItem value="medium">Średni</SelectItem>
            <SelectItem value="low">Niski</SelectItem>
          </SelectContent>
        </Select>

        <Select value={category} onValueChange={(v) => setCategory(v as Category | '')}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Wszystkie kategorie" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Wszystkie kategorie</SelectItem>
            <SelectItem value="maintenance">Usterka</SelectItem>
            <SelectItem value="payment">Płatność</SelectItem>
            <SelectItem value="noise_complaint">Hałas</SelectItem>
            <SelectItem value="lease">Najem</SelectItem>
            <SelectItem value="general">Ogólne</SelectItem>
            <SelectItem value="supplier">Dostawca</SelectItem>
            <SelectItem value="other">Inne</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Tabela */}
      {isError && (
        <p className="text-sm text-red-600 mb-4">Błąd ładowania wątków. Czy backend jest uruchomiony?</p>
      )}

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-4 font-medium">Priorytet</th>
            <th className="py-2 pr-4 font-medium">Kategoria</th>
            <th className="py-2 pr-4 font-medium">Nadawca</th>
            <th className="py-2 pr-4 font-medium">Podgląd</th>
            <th className="py-2 pr-4 font-medium">Status</th>
            <th className="py-2 font-medium">Zaktualizowano</th>
          </tr>
        </thead>
        <tbody>
          {isLoading &&
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b">
                <td className="py-3 pr-4"><Skeleton className="h-5 w-16" /></td>
                <td className="py-3 pr-4"><Skeleton className="h-5 w-24" /></td>
                <td className="py-3 pr-4"><Skeleton className="h-5 w-32" /></td>
                <td className="py-3 pr-4"><Skeleton className="h-5 w-48" /></td>
                <td className="py-3 pr-4"><Skeleton className="h-5 w-20" /></td>
                <td className="py-3"><Skeleton className="h-5 w-20" /></td>
              </tr>
            ))}

          {!isLoading && data?.items.length === 0 && (
            <tr>
              <td colSpan={6} className="py-8 text-center text-muted-foreground">
                Brak wątków.
              </td>
            </tr>
          )}

          {data?.items.map((thread) => (
            <tr
              key={thread.id}
              className="border-b hover:bg-muted/40 cursor-pointer"
              onClick={() => navigate(`/threads/${thread.id}`)}
            >
              <td className="py-3 pr-4">
                <Badge className={PRIORITY_CLASS[thread.priority]}>{PRIORITY_LABEL[thread.priority]}</Badge>
              </td>
              <td className="py-3 pr-4 text-muted-foreground">
                {thread.category ? (CATEGORY_LABEL[thread.category] ?? thread.category) : '—'}
              </td>
              <td className="py-3 pr-4 font-mono text-xs">{sender(thread)}</td>
              <td className="py-3 pr-4 text-muted-foreground max-w-xs truncate">{preview(thread)}</td>
              <td className="py-3 pr-4">
                <Badge className={STATUS_CLASS[thread.status]}>{STATUS_LABEL[thread.status]}</Badge>
              </td>
              <td className="py-3 text-muted-foreground text-xs">
                {formatDistanceToNow(new Date(thread.updated_at), { addSuffix: true, locale: pl })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
