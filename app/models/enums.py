import enum


class Channel(str, enum.Enum):
    email = "email"
    sms = "sms"
    voicemail = "voicemail"


class SenderType(str, enum.Enum):
    resident = "resident"
    supplier = "supplier"
    board = "board"
    unknown = "unknown"


class Category(str, enum.Enum):
    maintenance = "maintenance"
    payment = "payment"
    noise_complaint = "noise_complaint"
    lease = "lease"
    general = "general"
    supplier = "supplier"
    other = "other"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Status(str, enum.Enum):
    new = "new"
    pending_review = "pending_review"
    replied = "replied"
    resolved = "resolved"
    escalated = "escalated"


class Action(str, enum.Enum):
    draft_reply = "draft_reply"
    escalate = "escalate"
    group_only = "group_only"
    no_action = "no_action"


class FeedbackType(str, enum.Enum):
    approved = "approved"
    corrected = "corrected"
    overridden = "overridden"
