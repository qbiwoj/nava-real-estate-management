// Enums — mirror app/models/enums.py exactly
export type Channel = 'email' | 'sms' | 'voicemail'
export type SenderType = 'resident' | 'supplier' | 'board' | 'unknown'
export type Category =
  | 'maintenance'
  | 'payment'
  | 'noise_complaint'
  | 'lease'
  | 'general'
  | 'supplier'
  | 'other'
export type Priority = 'low' | 'medium' | 'high' | 'urgent'
export type Status = 'new' | 'pending_review' | 'replied' | 'resolved' | 'escalated'
export type Action = 'draft_reply' | 'escalate' | 'group_only' | 'no_action'
export type FeedbackType = 'approved' | 'corrected' | 'overridden'

// Data shapes — mirror backend Pydantic schemas
export interface Message {
  id: string
  channel: Channel
  raw_content: string
  subject: string | null
  sender_ref: string
  sender_type: SenderType
  transcription: string | null
  transcription_confidence: number | null
  received_at: string // ISO8601
}

export interface AgentDecision {
  id: string
  thread_id: string
  action: Action
  rationale: string
  draft_reply: string | null
  model_id: string
  few_shot_ids: string[]
  is_current: boolean
  created_at: string
}

export interface AdminFeedback {
  id: string
  decision_id: string
  feedback_type: FeedbackType
  original_action: Action
  corrected_action: Action | null
  original_draft: string | null
  corrected_draft: string | null
  correction_note: string | null
  created_at: string
}

export interface Thread {
  id: string
  category: Category | null
  priority: Priority
  status: Status
  created_at: string
  updated_at: string
  messages: Message[]
  current_decision: AgentDecision | null
  feedback_history: AdminFeedback[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ThreadFilters {
  status?: Status
  priority?: Priority
  category?: Category
  page?: number
  size?: number
}

export interface FeedbackPayload {
  feedback_type: FeedbackType
  corrected_action?: Action
  corrected_draft?: string
  correction_note?: string
}

export interface SendReplyPayload {
  channel: 'email' | 'sms'
  final_body: string
}
