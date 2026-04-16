import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.logging_config import configure_logging
from app.routers.admin import router as admin_router
from app.routers.decisions import router as decisions_router
from app.routers.feedback import router as feedback_router
from app.routers.replies import router as replies_router
from app.routers.threads import router as threads_router
from app.routers.voice import router as voice_router
from app.routers.webhooks import router as webhooks_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("application_startup", extra={"event": "startup"})
    yield
    logger.info("application_shutdown", extra={"event": "shutdown"})


app = FastAPI(title="Nava Real Estate Management", lifespan=lifespan)

app.include_router(webhooks_router)
app.include_router(threads_router)
app.include_router(decisions_router)
app.include_router(feedback_router)
app.include_router(replies_router)
app.include_router(voice_router)
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
