from fastapi import FastAPI

app = FastAPI(title="Nava Real Estate Management")


@app.get("/health")
async def health():
    return {"status": "ok"}
