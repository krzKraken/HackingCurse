import json
import secrets

import redis

from app.config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def create_session(user_id: str, mfa_verified: bool, ttl_seconds: int) -> str:
    session_id = secrets.token_urlsafe(32)
    data = {"user_id": user_id, "mfa_verified": mfa_verified}
    redis_client.setex(f"session:{session_id}", ttl_seconds, json.dumps(data))
    return session_id


def get_session(session_id: str) -> dict | None:
    raw = redis_client.get(f"session:{session_id}")
    if raw is None:
        return None
    return json.loads(raw)


def upgrade_session(session_id: str, ttl_seconds: int) -> None:
    data = get_session(session_id)
    if data is None:
        raise ValueError("session not found")
    data["mfa_verified"] = True
    redis_client.setex(f"session:{session_id}", ttl_seconds, json.dumps(data))


def delete_session(session_id: str) -> None:
    redis_client.delete(f"session:{session_id}")
