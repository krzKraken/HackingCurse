from fastapi import FastAPI

from app.auth.router import router as auth_router

app = FastAPI(title="CyberLearn API")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
