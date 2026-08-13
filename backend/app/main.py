from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.content.router import router as content_router
from app.dashboard.router import router as dashboard_router
from app.notes.router import router as notes_router
from app.reviews.router import router as reviews_router

app = FastAPI(title="CyberLearn API")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(content_router, prefix="/api/v1/content", tags=["content"])
app.include_router(notes_router, prefix="/api/v1/notes", tags=["notes"])
app.include_router(reviews_router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
