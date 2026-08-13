from fastapi import FastAPI

app = FastAPI(title="CyberLearn API")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
