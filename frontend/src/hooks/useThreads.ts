import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getThreads, getThread, runAgent, submitFeedback, sendReply, getAdminStats } from '@/lib/api'
import type { ThreadFilters, FeedbackPayload, SendReplyPayload } from '@/lib/types'

export function useThreads(filters: ThreadFilters = {}) {
  return useQuery({
    queryKey: ['threads', filters],
    queryFn: () => getThreads(filters),
    refetchInterval: 30_000,
  })
}

export function useThread(id: string) {
  return useQuery({
    queryKey: ['thread', id],
    queryFn: () => getThread(id),
    refetchInterval: 2_000,
    enabled: !!id,
  })
}

export function useRunAgent(threadId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => runAgent(threadId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['thread', threadId] }),
  })
}

export function useSubmitFeedback(threadId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: FeedbackPayload) => submitFeedback(threadId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['thread', threadId] })
      qc.invalidateQueries({ queryKey: ['threads'] })
    },
  })
}

export function useAdminStats() {
  return useQuery({
    queryKey: ['admin-stats'],
    queryFn: getAdminStats,
    refetchInterval: 60_000,
  })
}

export function useSendReply(threadId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: SendReplyPayload) => sendReply(threadId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['thread', threadId] })
      qc.invalidateQueries({ queryKey: ['threads'] })
    },
  })
}
