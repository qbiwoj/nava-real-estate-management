import type {
  Thread,
  PaginatedResponse,
  ThreadFilters,
  FeedbackPayload,
  SendReplyPayload,
  DemoMessagePayload,
  AdminStats,
} from './types'

const BASE = '/api/v1'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

export function getThreads(filters: ThreadFilters = {}): Promise<PaginatedResponse<Thread>> {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.priority) params.set('priority', filters.priority)
  if (filters.category) params.set('category', filters.category)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.size) params.set('size', String(filters.size ?? 50))
  const qs = params.toString()
  return apiFetch(`/threads${qs ? `?${qs}` : ''}`)
}

export function getThread(id: string): Promise<Thread> {
  return apiFetch(`/threads/${id}`)
}

export function patchThread(id: string, data: { status?: string; priority?: string }): Promise<Thread> {
  return apiFetch(`/threads/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function runAgent(id: string): Promise<void> {
  return apiFetch(`/threads/${id}/run-agent`, { method: 'POST' })
}

export function runUnprocessed(): Promise<{ queued: number }> {
  return apiFetch('/threads/run-unprocessed', { method: 'POST' })
}

export function submitFeedback(id: string, payload: FeedbackPayload): Promise<void> {
  return apiFetch(`/threads/${id}/feedback`, { method: 'POST', body: JSON.stringify(payload) })
}

export function sendReply(id: string, payload: SendReplyPayload): Promise<void> {
  return apiFetch(`/threads/${id}/send-reply`, { method: 'POST', body: JSON.stringify(payload) })
}

export function sendDemoMessage(payload: DemoMessagePayload): Promise<{ message_id: string; thread_id: string }> {
  const { channel, ...rest } = payload
  return apiFetch(`/webhooks/${channel}`, { method: 'POST', body: JSON.stringify(rest) })
}

export function getAdminStats(): Promise<AdminStats> {
  return apiFetch('/admin/stats')
}

export function getBriefingText(): Promise<{ text: string; threads_covered: string[] }> {
  return apiFetch('/voice/briefing-text')
}

export async function getBriefingAudio(): Promise<string> {
  const res = await fetch('/api/v1/voice/briefing-audio')
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}
