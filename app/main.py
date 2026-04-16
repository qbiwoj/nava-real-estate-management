from fastapi import FastAPI

from app.routers.decisions import router as decisions_router
from app.routers.threads import router as threads_router
from app.routers.webhooks import router as webhooks_router

app = FastAPI(title="Nava Real Estate Management")

app.include_router(webhooks_router)
app.include_router(threads_router)
app.include_router(decisions_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
