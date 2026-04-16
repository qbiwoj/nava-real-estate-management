import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { pl } from 'date-fns/locale'
import { Mail, MessageSquare, Phone, ArrowLeft, AlertTriangle } from 'lucide-react'
import { useThread, useRunAgent, useSubmitFeedback, useSendReply } from '@/hooks/useThreads'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import { Spinner } from '@/components/ui/spinner'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Action, Priority, Status, Message } from '@/lib/types'

const PRIORITY_CLASS: Record<Priority, string> = {
  urgent: 'bg-red-100 text-red-800',
  high: 'bg-orange-100 text-orange-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-700',
}

const STATUS_CLASS: Record<Status, string> = {
  new: 'bg-blue-100 text-blue-800',
  pending_review: 'bg-amber-100 text-amber-800',
  replied: 'bg-green-100 text-green-800',
  resolved: 'bg-gray-100 text-gray-600',
  escalated: 'bg-red-100 text-red-800',
}

const ACTION_CLASS: Record<Action, string> = {
  draft_reply: 'bg-blue-100 text-blue-800',
  escalate: 'bg-red-100 text-red-800',
  group_only: 'bg-yellow-100 text-yellow-800',
  no_action: 'bg-gray-100 text-gray-600',
}

const PRIORITY_LABEL: Record<string, string> = {
  urgent: 'Pilny', high: 'Wysoki', medium: 'Średni', low: 'Niski',
}
const STATUS_LABEL: Record<string, string> = {
  new: 'Nowy', pending_review: 'Do sprawdzenia', replied: 'Odpowiedziano',
  resolved: 'Zamknięty', escalated: 'Eskalowany',
}
const ACTION_LABEL: Record<Action, string> = {
  draft_reply: 'Projekt odpowiedzi',
  escalate: 'Eskalacja',
  group_only: 'Tylko grupowanie',
  no_action: 'Brak działania',
}
const CATEGORY_LABEL: Record<string, string> = {
  maintenance: 'Usterka', payment: 'Płatność', noise_complaint: 'Hałas',
  lease: 'Najem', general: 'Ogólne', supplier: 'Dostawca', other: 'Inne',
}
const SENDER_TYPE_LABEL: Record<string, string> = {
  resident: 'lokator', supplier: 'dostawca', board: 'zarząd', unknown: 'nieznany',
}

const CHANNEL_ICON: Record<Message['channel'], React.ReactNode> = {
  email: <Mail size={14} />,
  sms: <MessageSquare size={14} />,
  voicemail: <Phone size={14} />,
}

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>()
  const { data: thread, isLoading, isError } = useThread(id!)

  const runAgent = useRunAgent(id!)
  const submitFeedback = useSubmitFeedback(id!)
  const sendReply = useSendReply(id!)

  // Draft editor state (local, pre-filled from decision)
  const [draft, setDraft] = useState<string>('')
  const [draftInitialized, setDraftInitialized] = useState(false)

  // Feedback form state
  const [showCorrectForm, setShowCorrectForm] = useState(false)
  const [correctedAction, setCorrectedAction] = useState<Action>('draft_reply')
  const [correctedDraft, setCorrectedDraft] = useState('')
  const [correctionNote, setCorrectionNote] = useState('')

  // Initialize draft from decision once loaded
  if (thread?.current_decision?.draft_reply && !draftInitialized) {
    setDraft(thread.current_decision.draft_reply)
    setDraftInitialized(true)
  }

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    )
  }

  if (isError || !thread) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Link to="/" className="text-sm text-muted-foreground hover:underline flex items-center gap-1 mb-4">
          <ArrowLeft size={14} /> Kolejka
        </Link>
        <p className="text-red-600 text-sm">Nie znaleziono wątku lub backend niedostępny.</p>
      </div>
    )
  }

  const done = thread.status === 'replied' || thread.status === 'resolved'
  const decision = thread.current_decision

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Link to="/" className="text-sm text-muted-foreground hover:underline flex items-center gap-1 mb-3">
          <ArrowLeft size={14} /> Kolejka
        </Link>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge className={PRIORITY_CLASS[thread.priority]}>{PRIORITY_LABEL[thread.priority] ?? thread.priority}</Badge>
          <Badge className={STATUS_CLASS[thread.status]}>{STATUS_LABEL[thread.status] ?? thread.status}</Badge>
          {thread.category && (
            <span className="text-sm text-muted-foreground">{CATEGORY_LABEL[thread.category] ?? thread.category}</span>
          )}
        </div>
      </div>

      {/* Messages */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Wiadomości</h2>
        {[...(thread.messages ?? [])]
          .sort((a, b) => new Date(a.received_at).getTime() - new Date(b.received_at).getTime())
          .map((msg) => (
            <div key={msg.id} className="border rounded-lg p-4 space-y-1">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {CHANNEL_ICON[msg.channel]}
                <span className="font-mono">{msg.sender_ref}</span>
                <span>·</span>
                <span>{formatDistanceToNow(new Date(msg.received_at), { addSuffix: true, locale: pl })}</span>
                <span>·</span>
                <span>{SENDER_TYPE_LABEL[msg.sender_type] ?? msg.sender_type}</span>
              </div>
              {msg.subject && (
                <p className="text-sm font-medium">{msg.subject}</p>
              )}
              <p className="text-sm whitespace-pre-wrap">
                {msg.transcription ?? msg.raw_content}
              </p>
              {msg.channel === 'voicemail' && msg.transcription_confidence !== null && (
                <div className="flex items-center gap-1 text-xs">
                  {msg.transcription_confidence < 0.8 ? (
                    <span className="flex items-center gap-1 text-amber-700">
                      <AlertTriangle size={12} />
                      Niska pewność transkrypcji ({Math.round(msg.transcription_confidence * 100)}%)
                    </span>
                  ) : (
                    <span className="text-muted-foreground">
                      Pewność transkrypcji: {Math.round(msg.transcription_confidence * 100)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
      </section>

      {/* Agent Decision */}
      <section className="space-y-3">
        <div className="flex items-center gap-2 justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Decyzja agenta</h2>
            {decision && (
              <Tooltip
                content={`Model: ${decision.model_id} · Koszt: $${decision.cost_usd?.toFixed(4)}`}
              />
            )}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => runAgent.mutate()}
            disabled={runAgent.isPending}
          >
            {decision ? 'Uruchom ponownie' : 'Uruchom'}
          </Button>
        </div>

        {runAgent.isPending ? (
          <div className="border rounded-lg overflow-hidden">
            <Spinner text="Agent analizuje wiadomości…" />
          </div>
        ) : !decision ? (
          <div className="border rounded-lg p-4 text-center text-sm text-muted-foreground">
            Agent jeszcze nie działał.
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 flex items-center gap-2 border-b bg-background">
              <Badge className={ACTION_CLASS[decision.action]}>{ACTION_LABEL[decision.action]}</Badge>
              {(decision.few_shot_ids?.length ?? 0) > 0 && (
                <span className="text-xs text-muted-foreground">
                  · {decision.few_shot_ids?.length} korekty
                </span>
              )}
            </div>

            {/* Rationale */}
            <div className="px-4 py-3 bg-muted/30">
              <div className="prose prose-sm max-w-none text-foreground
                prose-p:my-1 prose-ul:my-1 prose-li:my-0
                prose-headings:text-foreground prose-headings:font-semibold
                prose-code:bg-muted prose-code:px-1 prose-code:rounded prose-code:text-xs
                prose-table:w-full prose-table:text-sm prose-table:border-collapse
                prose-thead:border-b
                prose-th:py-1.5 prose-th:px-2 prose-th:text-left prose-th:font-medium prose-th:text-muted-foreground
                prose-td:py-1.5 prose-td:px-2 prose-td:border-b prose-td:border-border/50">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{decision.rationale}</ReactMarkdown>
              </div>
            </div>

          </div>
        )}
      </section>

      {/* Draft reply */}
      {decision?.action === 'draft_reply' && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Projekt odpowiedzi</h2>
          <div className="border rounded-lg overflow-hidden">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={5}
              disabled={done}
              placeholder="Projekt odpowiedzi…"
              className="border-0 rounded-none focus-visible:ring-0 resize-none"
            />
            <div className="px-3 py-2 border-t bg-muted/20 flex items-center gap-3">
              <Button
                size="sm"
                onClick={() => sendReply.mutate({ channel: 'sms', final_body: draft })}
                disabled={!draft.trim() || done || sendReply.isPending}
              >
                {sendReply.isPending ? 'Wysyłanie…' : 'Wyślij odpowiedź'}
              </Button>
              {done && (
                <p className="text-xs text-muted-foreground">Odpowiedź już wysłana.</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Feedback */}
      {decision && !done && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Ocena</h2>
          <div className="border rounded-lg p-4 space-y-3">
            {!showCorrectForm ? (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="border-green-400 text-green-700 hover:bg-green-50"
                  onClick={() => submitFeedback.mutate({ feedback_type: 'approved' })}
                  disabled={submitFeedback.isPending}
                >
                  {submitFeedback.isPending ? 'Zapisywanie…' : 'Zatwierdź'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-400 text-red-700 hover:bg-red-50"
                  onClick={() => {
                    setCorrectedAction(decision.action)
                    setCorrectedDraft(decision.draft_reply ?? '')
                    setShowCorrectForm(true)
                  }}
                >
                  Popraw
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Właściwe działanie</label>
                  <Select
                    value={correctedAction}
                    onValueChange={(v) => setCorrectedAction(v as Action)}
                  >
                    <SelectTrigger className="w-52">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft_reply">Projekt odpowiedzi</SelectItem>
                      <SelectItem value="escalate">Eskalacja</SelectItem>
                      <SelectItem value="group_only">Tylko grupowanie</SelectItem>
                      <SelectItem value="no_action">Brak działania</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {correctedAction === 'draft_reply' && (
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Poprawiona odpowiedź</label>
                    <Textarea
                      value={correctedDraft}
                      onChange={(e) => setCorrectedDraft(e.target.value)}
                      rows={3}
                      placeholder="Poprawiony projekt odpowiedzi…"
                    />
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Co było nie tak? (opcjonalnie)</label>
                  <Textarea
                    value={correctionNote}
                    onChange={(e) => setCorrectionNote(e.target.value)}
                    rows={2}
                    placeholder="np. powinna być eskalacja, zły ton…"
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() =>
                      submitFeedback.mutate({
                        feedback_type: 'corrected',
                        corrected_action: correctedAction,
                        corrected_draft: correctedAction === 'draft_reply' ? correctedDraft : undefined,
                        correction_note: correctionNote || undefined,
                      })
                    }
                    disabled={submitFeedback.isPending}
                  >
                    {submitFeedback.isPending ? 'Zapisywanie…' : 'Zapisz korektę'}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowCorrectForm(false)}>
                    Anuluj
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
