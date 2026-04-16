from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.database import get_session
from app.models import AgentDecision, Thread
from app.services.costs import compute_llm_cost

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    # Thread counts by status / priority / category
    status_rows = await session.execute(
        select(Thread.status, func.count().label("n")).group_by(Thread.status)
    )
    priority_rows = await session.execute(
        select(Thread.priority, func.count().label("n")).group_by(Thread.priority)
    )
    category_rows = await session.execute(
        select(Thread.category, func.count().label("n")).group_by(Thread.category)
    )

    # Cost aggregates from current decisions
    cost_rows = await session.execute(
        select(
            AgentDecision.model_id,
            func.count().label("runs"),
            func.sum(AgentDecision.input_tokens).label("input_tokens"),
            func.sum(AgentDecision.output_tokens).label("output_tokens"),
            func.sum(AgentDecision.cache_read_tokens).label("cache_read_tokens"),
            func.sum(AgentDecision.cache_creation_tokens).label("cache_creation_tokens"),
        )
        .where(AgentDecision.is_current == True)  # noqa: E712
        .group_by(AgentDecision.model_id)
    )

    total_cost = 0.0
    total_runs = 0
    cost_by_model: dict = {}

    for row in cost_rows.all():
        model_cost = compute_llm_cost(
            row.model_id,
            row.input_tokens or 0,
            row.output_tokens or 0,
            row.cache_read_tokens or 0,
            row.cache_creation_tokens or 0,
        )
        total_cost += model_cost
        total_runs += row.runs
        cost_by_model[row.model_id] = {
            "runs": row.runs,
            "cost_usd": round(model_cost, 6),
        }

    return {
        "by_status": {r.status.value: r.n for r in status_rows.all()},
        "by_priority": {r.priority.value: r.n for r in priority_rows.all()},
        "by_category": {r.category.value: r.n for r in category_rows.all() if r.category is not None},
        "costs": {
            "agent_total_usd": round(total_cost, 6),
            "agent_runs": total_runs,
            "avg_cost_per_run_usd": round(total_cost / total_runs, 6) if total_runs else 0.0,
            "by_model": cost_by_model,
        },
    }
