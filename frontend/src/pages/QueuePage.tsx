import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { pl } from 'date-fns/locale'
import { useThreads } from '@/hooks/useThreads'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
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
  const msg = [...thread.messages].sort(
    (a, b) => new Date(b.received_at).getTime() - new Date(a.received_at).getTime(),
  )[0]
  if (!msg) return '—'
  const text = msg.transcription ?? msg.raw_content
  return text.length > 80 ? text.slice(0, 80) + '…' : text
}

function sender(thread: Thread): string {
  return thread.messages[0]?.sender_ref ?? '—'
}

export default function QueuePage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<Status | ''>('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [category, setCategory] = useState<Category | ''>('')

  const { data, isLoading, isError } = useThreads({
    status: status || undefined,
    priority: priority || undefined,
    category: category || undefined,
  })

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-xl font-semibold mb-4">Kolejka wiadomości</h1>

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
