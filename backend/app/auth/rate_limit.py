from app.auth.sessions import redis_client
from app.config import settings


def register_failed_attempt(key: str) -> int:
    redis_key = f"login_fail:{key}"
    pipe = redis_client.pipeline()
    pipe.incr(redis_key)
    pipe.expire(redis_key, settings.login_lockout_seconds)
    count, _ = pipe.execute()
    return int(count)


def is_locked_out(key: str) -> bool:
    count = redis_client.get(f"login_fail:{key}")
    return count is not None and int(count) >= settings.login_max_attempts


def clear_failed_attempts(key: str) -> None:
    redis_client.delete(f"login_fail:{key}")
