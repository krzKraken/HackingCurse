from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.content.router import router as content_router

app = FastAPI(title="CyberLearn API")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(content_router, prefix="/api/v1/content", tags=["content"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
