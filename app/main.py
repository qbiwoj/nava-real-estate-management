from fastapi import FastAPI

from app.routers.webhooks import router as webhooks_router

app = FastAPI(title="Nava Real Estate Management")

app.include_router(webhooks_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
