"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-07
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("CREATE TYPE channel AS ENUM ('email', 'sms', 'voicemail')")
    op.execute("CREATE TYPE sendertype AS ENUM ('resident', 'supplier', 'board', 'unknown')")
    op.execute("CREATE TYPE category AS ENUM ('maintenance', 'payment', 'noise_complaint', 'lease', 'general', 'supplier', 'other')")
    op.execute("CREATE TYPE priority AS ENUM ('low', 'medium', 'high', 'urgent')")
    op.execute("CREATE TYPE status AS ENUM ('new', 'pending_review', 'replied', 'resolved', 'escalated')")
    op.execute("CREATE TYPE action AS ENUM ('draft_reply', 'escalate', 'group_only', 'no_action')")
    op.execute("CREATE TYPE feedbacktype AS ENUM ('approved', 'corrected', 'overridden')")

    op.execute("""
        CREATE TABLE messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            channel channel NOT NULL,
            raw_content TEXT NOT NULL,
            transcription TEXT,
            subject VARCHAR(500),
            sender_ref VARCHAR(500) NOT NULL,
            sender_type sendertype NOT NULL,
            transcription_confidence FLOAT,
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            embedding vector(1536)
        )
    """)
    op.execute("CREATE INDEX ON messages USING hnsw (embedding vector_cosine_ops)")

    op.execute("""
        CREATE TABLE threads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category category,
            priority priority NOT NULL DEFAULT 'low',
            status status NOT NULL DEFAULT 'new',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE thread_messages (
            thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            PRIMARY KEY (thread_id, message_id)
        )
    """)

    op.execute("""
        CREATE TABLE agent_decisions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            action action NOT NULL,
            rationale TEXT NOT NULL,
            draft_reply TEXT,
            model_id TEXT NOT NULL,
            few_shot_ids UUID[] NOT NULL DEFAULT '{}',
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE admin_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            decision_id UUID NOT NULL REFERENCES agent_decisions(id) ON DELETE CASCADE,
            feedback_type feedbacktype NOT NULL,
            original_action action NOT NULL,
            corrected_action action,
            original_draft TEXT,
            corrected_draft TEXT,
            correction_note TEXT,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ON admin_feedback USING hnsw (embedding vector_cosine_ops)")

    op.execute("""
        CREATE TABLE outbound_replies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            final_body TEXT NOT NULL,
            channel channel NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE voice_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            call_sid VARCHAR(255) NOT NULL UNIQUE,
            briefing_text TEXT NOT NULL,
            threads_covered UUID[] NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS voice_sessions")
    op.execute("DROP TABLE IF EXISTS outbound_replies")
    op.execute("DROP TABLE IF EXISTS admin_feedback")
    op.execute("DROP TABLE IF EXISTS agent_decisions")
    op.execute("DROP TABLE IF EXISTS thread_messages")
    op.execute("DROP TABLE IF EXISTS threads")
    op.execute("DROP TABLE IF EXISTS messages")

    op.execute("DROP TYPE IF EXISTS feedbacktype")
    op.execute("DROP TYPE IF EXISTS action")
    op.execute("DROP TYPE IF EXISTS status")
    op.execute("DROP TYPE IF EXISTS priority")
    op.execute("DROP TYPE IF EXISTS category")
    op.execute("DROP TYPE IF EXISTS sendertype")
    op.execute("DROP TYPE IF EXISTS channel")
