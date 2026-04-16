from fastapi import FastAPI

from app.routers.decisions import router as decisions_router
from app.routers.feedback import router as feedback_router
from app.routers.replies import router as replies_router
from app.routers.threads import router as threads_router
from app.routers.voice import router as voice_router
from app.routers.webhooks import router as webhooks_router

app = FastAPI(title="Nava Real Estate Management")

app.include_router(webhooks_router)
app.include_router(threads_router)
app.include_router(decisions_router)
app.include_router(feedback_router)
app.include_router(replies_router)
app.include_router(voice_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
