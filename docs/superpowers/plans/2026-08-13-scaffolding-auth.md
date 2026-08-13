# Scaffolding + Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the CyberLearn backend and frontend skeletons with a fully working login flow (username/password + MFA TOTP) backed by Postgres and Redis, so every later sub-plan has a real app to attach to.

**Architecture:** FastAPI monolith (modular by feature) talking to PostgreSQL via SQLAlchemy 2.0 + Alembic migrations, and to Redis for session storage and login rate limiting. Sessions are opaque random tokens stored server-side in Redis (not JWTs) with an `httpOnly`/`secure`/`SameSite=strict` cookie. Frontend is a React + Vite SPA using React Router, talking to the API via `fetch` with `credentials: "include"`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, psycopg3, argon2-cffi, pyotp, redis-py, pytest + httpx; Node 20, React 18, Vite, TypeScript, react-router-dom.

## Global Constraints

- Cookies: `httpOnly`, `secure`, `SameSite=strict` (spec §4 threat model).
- Passwords: hashed with Argon2, never stored/logged in plaintext.
- MFA (TOTP) is mandatory for every login — no path that skips it (spec §0 decisions).
- No public self-registration endpoint — single OWNER account, created via CLI script only (single-user platform, spec §135).
- Login endpoint must be rate-limited with lockout (spec §4 threat model: brute force / credential stuffing).
- All API routes live under `/api/v1/...` (spec §137).

---

## File Structure

```
backend/
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py
│   └── auth/
│       ├── __init__.py
│       ├── security.py       # Argon2 hashing
│       ├── totp.py           # TOTP generation/verification
│       ├── sessions.py       # Redis-backed session store
│       ├── rate_limit.py     # login attempt tracking
│       ├── schemas.py        # Pydantic request/response models
│       ├── dependencies.py   # get_current_user
│       └── router.py         # /login, /mfa/verify, /me, /logout
├── scripts/
│   └── create_owner.py       # CLI to create the single OWNER user
└── tests/
    ├── conftest.py
    └── auth/
        ├── test_security.py
        ├── test_totp.py
        └── test_router.py

frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── lib/
    │   └── api.ts
    └── features/
        └── auth/
            ├── useAuth.tsx
            ├── ProtectedRoute.tsx
            ├── LoginPage.tsx
            └── MfaPage.tsx

docker-compose.yml
docker/postgres-init/01-create-test-db.sql
```

---

### Task 1: Repo scaffolding — Postgres + Redis via Docker Compose, FastAPI boots

**Files:**
- Create: `docker-compose.yml`
- Create: `docker/postgres-init/01-create-test-db.sql`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

**Interfaces:**
- Produces: `app.config.settings` (a `Settings` instance with `database_url`, `redis_url`, `cookie_name`, `cookie_secure`, `session_ttl_pending_seconds`, `session_ttl_authenticated_seconds`, `login_max_attempts`, `login_lockout_seconds`).
- Produces: `app.main.app` — the FastAPI instance, with `GET /api/v1/health` returning `{"status": "ok"}`.

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: cyberlearn
      POSTGRES_PASSWORD: cyberlearn
      POSTGRES_DB: cyberlearn
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres-init:/docker-entrypoint-initdb.d

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

- [ ] **Step 2: Write the test-database init script**

`docker/postgres-init/01-create-test-db.sql`:
```sql
CREATE DATABASE cyberlearn_test;
```

- [ ] **Step 3: Write `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
alembic==1.14.0
psycopg[binary]==3.2.3
pydantic-settings==2.6.1
argon2-cffi==23.1.0
pyotp==2.9.0
redis==5.2.0
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 4: Write `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://cyberlearn:cyberlearn@localhost:5432/cyberlearn"
    redis_url: str = "redis://localhost:6379/0"
    cookie_name: str = "cl_session"
    cookie_secure: bool = True
    session_ttl_pending_seconds: int = 300
    session_ttl_authenticated_seconds: int = 60 * 60 * 24 * 7
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
```

- [ ] **Step 5: Write `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="CyberLearn API")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: Bring up infra and verify the API boots**

Run:
```bash
cd docker-compose.yml's directory
docker compose up -d postgres redis
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload
```
In another shell: `curl http://localhost:8000/api/v1/health`
Expected: `{"status":"ok"}`

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml docker/postgres-init backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/main.py
git commit -m "feat: scaffold FastAPI app with Postgres/Redis via docker-compose"
```

---

### Task 2: Database engine + Alembic

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`

**Interfaces:**
- Consumes: `app.config.settings` (Task 1).
- Produces: `app.db.Base` (SQLAlchemy `DeclarativeBase` subclass, used by every model), `app.db.SessionLocal` (sessionmaker), `app.db.get_db` (FastAPI dependency yielding a `Session`).

- [ ] **Step 1: Write `backend/app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Initialize Alembic**

Run:
```bash
cd backend
alembic init alembic
```

- [ ] **Step 3: Replace `backend/alembic/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base
from app.models import user  # noqa: F401 — registers User with Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

This references `app.models.user`, which doesn't exist yet — that's Task 3. This task's verification step only checks Alembic loads config correctly; the import will be added and verified in Task 3.

- [ ] **Step 4: Commit**

```bash
git add backend/app/db.py backend/alembic.ini backend/alembic
git commit -m "feat: add SQLAlchemy engine and Alembic setup"
```

---

### Task 3: User model + first migration

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/alembic/versions/0001_create_users.py`

**Interfaces:**
- Consumes: `app.db.Base` (Task 2).
- Produces: `app.models.user.User` with fields `id: uuid.UUID`, `username: str`, `password_hash: str`, `totp_secret: str`, `created_at: datetime`.

- [ ] **Step 1: Write `backend/app/models/user.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Generate and review the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "create users"
```
Rename the generated file to `backend/alembic/versions/0001_create_users.py` if needed, and confirm it contains a `users` table with the columns above.

- [ ] **Step 3: Apply the migration and verify**

Run:
```bash
alembic upgrade head
psql postgresql://cyberlearn:cyberlearn@localhost:5432/cyberlearn -c "\d users"
```
Expected: table `users` exists with columns `id, username, password_hash, totp_secret, created_at`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models backend/alembic/versions
git commit -m "feat: add User model and initial migration"
```

---

### Task 4: Password hashing (Argon2)

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/security.py`
- Test: `backend/tests/auth/test_security.py`

**Interfaces:**
- Produces: `app.auth.security.hash_password(password: str) -> str`, `app.auth.security.verify_password(password: str, password_hash: str) -> bool`.

- [ ] **Step 1: Write the failing test**

`backend/tests/auth/test_security.py`:
```python
from app.auth.security import hash_password, verify_password


def test_verify_password_correct():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/auth/test_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.security'`

- [ ] **Step 3: Write `backend/app/auth/security.py`**

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/auth/test_security.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/__init__.py backend/app/auth/security.py backend/tests/auth/test_security.py
git commit -m "feat: add Argon2 password hashing"
```

---

### Task 5: TOTP service

**Files:**
- Create: `backend/app/auth/totp.py`
- Test: `backend/tests/auth/test_totp.py`

**Interfaces:**
- Produces: `app.auth.totp.generate_totp_secret() -> str`, `app.auth.totp.totp_provisioning_uri(secret: str, username: str, issuer: str = "CyberLearn") -> str`, `app.auth.totp.verify_totp_code(secret: str, code: str) -> bool`.

- [ ] **Step 1: Write the failing test**

`backend/tests/auth/test_totp.py`:
```python
import pyotp

from app.auth.totp import generate_totp_secret, verify_totp_code


def test_verify_totp_code_valid():
    secret = generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, code) is True


def test_verify_totp_code_invalid():
    secret = generate_totp_secret()
    assert verify_totp_code(secret, "000000") is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/auth/test_totp.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.totp'`

- [ ] **Step 3: Write `backend/app/auth/totp.py`**

```python
import pyotp


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, username: str, issuer: str = "CyberLearn") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/auth/test_totp.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/totp.py backend/tests/auth/test_totp.py
git commit -m "feat: add TOTP generation and verification"
```

---

### Task 6: Redis session store

**Files:**
- Create: `backend/app/auth/sessions.py`
- Test: `backend/tests/auth/test_sessions.py`

**Interfaces:**
- Consumes: `app.config.settings.redis_url` (Task 1).
- Produces: `app.auth.sessions.create_session(user_id: str, mfa_verified: bool, ttl_seconds: int) -> str`, `get_session(session_id: str) -> dict | None`, `upgrade_session(session_id: str, ttl_seconds: int) -> None`, `delete_session(session_id: str) -> None`, and the module-level `app.auth.sessions.redis_client` (needed by Task 7's rate limiter and by tests to flush state).

**Note:** this test requires Redis running (`docker compose up -d redis` from Task 1) — it is an integration test, not a pure unit test.

- [ ] **Step 1: Write the failing test**

`backend/tests/auth/test_sessions.py`:
```python
from app.auth.sessions import create_session, get_session, upgrade_session, delete_session


def test_create_and_get_session():
    session_id = create_session("user-1", mfa_verified=False, ttl_seconds=60)
    data = get_session(session_id)
    assert data == {"user_id": "user-1", "mfa_verified": False}


def test_upgrade_session_marks_mfa_verified():
    session_id = create_session("user-1", mfa_verified=False, ttl_seconds=60)
    upgrade_session(session_id, ttl_seconds=120)
    data = get_session(session_id)
    assert data["mfa_verified"] is True


def test_delete_session_removes_it():
    session_id = create_session("user-1", mfa_verified=False, ttl_seconds=60)
    delete_session(session_id)
    assert get_session(session_id) is None


def test_get_missing_session_returns_none():
    assert get_session("does-not-exist") is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/auth/test_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.sessions'`

- [ ] **Step 3: Write `backend/app/auth/sessions.py`**

```python
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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/auth/test_sessions.py -v` (with `docker compose up -d redis` running)
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/sessions.py backend/tests/auth/test_sessions.py
git commit -m "feat: add Redis-backed session store"
```

---

### Task 7: Login rate limiting

**Files:**
- Create: `backend/app/auth/rate_limit.py`
- Test: `backend/tests/auth/test_rate_limit.py`

**Interfaces:**
- Consumes: `app.config.settings.login_max_attempts`, `app.config.settings.login_lockout_seconds` (Task 1); `app.auth.sessions.redis_client` (Task 6).
- Produces: `app.auth.rate_limit.register_failed_attempt(key: str) -> int`, `is_locked_out(key: str) -> bool`, `clear_failed_attempts(key: str) -> None`.

- [ ] **Step 1: Write the failing test**

`backend/tests/auth/test_rate_limit.py`:
```python
from app.auth.rate_limit import register_failed_attempt, is_locked_out, clear_failed_attempts


def test_not_locked_out_initially():
    assert is_locked_out("someuser") is False


def test_locks_out_after_max_attempts():
    for _ in range(5):
        register_failed_attempt("bruteforced-user")
    assert is_locked_out("bruteforced-user") is True


def test_clear_failed_attempts_removes_lockout():
    for _ in range(5):
        register_failed_attempt("recovering-user")
    clear_failed_attempts("recovering-user")
    assert is_locked_out("recovering-user") is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/auth/test_rate_limit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth.rate_limit'`

- [ ] **Step 3: Write `backend/app/auth/rate_limit.py`**

```python
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
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/auth/test_rate_limit.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/rate_limit.py backend/tests/auth/test_rate_limit.py
git commit -m "feat: add login rate limiting with Redis-backed lockout"
```

---

### Task 8: Auth schemas, dependencies, and router (login / mfa / me / logout)

**Files:**
- Create: `backend/app/auth/schemas.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/auth/router.py`
- Modify: `backend/app/main.py` — mount the auth router
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/auth/__init__.py`
- Test: `backend/tests/auth/test_router.py`

**Interfaces:**
- Consumes: `hash_password`/`verify_password` (Task 4), `verify_totp_code` (Task 5), `create_session`/`get_session`/`upgrade_session`/`delete_session` (Task 6), `register_failed_attempt`/`is_locked_out`/`clear_failed_attempts` (Task 7), `app.models.user.User` (Task 3), `app.db.get_db` (Task 2).
- Produces: `app.auth.dependencies.get_current_user` (FastAPI dependency, used by every future protected route in later sub-plans), routes `POST /api/v1/auth/login`, `POST /api/v1/auth/mfa/verify`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.

- [ ] **Step 1: Write `backend/app/auth/schemas.py`**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    mfa_required: bool


class MfaVerifyRequest(BaseModel):
    code: str


class UserOut(BaseModel):
    id: str
    username: str
```

- [ ] **Step 2: Write `backend/app/auth/dependencies.py`**

```python
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.sessions import get_session
from app.config import settings
from app.db import get_db
from app.models.user import User


def get_current_user(
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> User:
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    session = get_session(session_id)
    if session is None or not session["mfa_verified"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user = db.get(User, session["user_id"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    return user
```

- [ ] **Step 3: Write `backend/app/auth/router.py`**

```python
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.rate_limit import clear_failed_attempts, is_locked_out, register_failed_attempt
from app.auth.schemas import LoginRequest, LoginResponse, MfaVerifyRequest, UserOut
from app.auth.security import verify_password
from app.auth.sessions import create_session, delete_session, get_session, upgrade_session
from app.auth.totp import verify_totp_code
from app.config import settings
from app.db import get_db
from app.models.user import User

router = APIRouter()


def _set_session_cookie(response: Response, session_id: str, max_age: int) -> None:
    response.set_cookie(
        settings.cookie_name,
        session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=max_age,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    if is_locked_out(payload.username):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts")

    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        register_failed_attempt(payload.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    clear_failed_attempts(payload.username)
    session_id = create_session(
        str(user.id), mfa_verified=False, ttl_seconds=settings.session_ttl_pending_seconds
    )
    _set_session_cookie(response, session_id, settings.session_ttl_pending_seconds)
    return LoginResponse(mfa_required=True)


@router.post("/mfa/verify", response_model=UserOut)
def mfa_verify(
    payload: MfaVerifyRequest,
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> UserOut:
    if session_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No pending session")

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

    user = db.get(User, session["user_id"])
    if user is None or not verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid MFA code")

    upgrade_session(session_id, settings.session_ttl_authenticated_seconds)
    _set_session_cookie(response, session_id, settings.session_ttl_authenticated_seconds)
    return UserOut(id=str(user.id), username=user.username)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=str(user.id), username=user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> None:
    if session_id:
        delete_session(session_id)
    response.delete_cookie(settings.cookie_name)
```

- [ ] **Step 4: Mount the router in `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.auth.router import router as auth_router

app = FastAPI(title="CyberLearn API")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: Write `backend/tests/conftest.py`**

```python
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://cyberlearn:cyberlearn@localhost:5432/cyberlearn_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.sessions import redis_client
from app.config import settings
from app.db import Base, get_db
from app.main import app

engine = create_engine(settings.database_url)
TestSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _clean_state():
    Base.metadata.create_all(engine)
    redis_client.flushdb()
    yield
    Base.metadata.drop_all(engine)
    redis_client.flushdb()


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Write the failing test**

`backend/tests/auth/test_router.py`:
```python
import pyotp

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret
from app.models.user import User


def _create_user(db_session, username="owner", password="s3cret-pass-1"):
    secret = generate_totp_secret()
    user = User(username=username, password_hash=hash_password(password), totp_secret=secret)
    db_session.add(user)
    db_session.commit()
    return user, password, secret


def test_login_then_mfa_verify_grants_access(client, db_session):
    user, password, secret = _create_user(db_session)

    login_resp = client.post("/api/v1/auth/login", json={"username": user.username, "password": password})
    assert login_resp.status_code == 200
    assert login_resp.json()["mfa_required"] is True

    me_before_mfa = client.get("/api/v1/auth/me")
    assert me_before_mfa.status_code == 401

    code = pyotp.TOTP(secret).now()
    mfa_resp = client.post("/api/v1/auth/mfa/verify", json={"code": code})
    assert mfa_resp.status_code == 200
    assert mfa_resp.json()["username"] == user.username

    me_after_mfa = client.get("/api/v1/auth/me")
    assert me_after_mfa.status_code == 200


def test_login_wrong_password_rejected(client, db_session):
    user, _password, _secret = _create_user(db_session)

    resp = client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrong"})
    assert resp.status_code == 401


def test_login_lockout_after_max_attempts(client, db_session):
    user, password, _secret = _create_user(db_session)

    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrong"})

    resp = client.post("/api/v1/auth/login", json={"username": user.username, "password": password})
    assert resp.status_code == 429


def test_logout_clears_session(client, db_session):
    user, password, secret = _create_user(db_session)
    client.post("/api/v1/auth/login", json={"username": user.username, "password": password})
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/auth/mfa/verify", json={"code": code})

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
```

- [ ] **Step 7: Run it to verify it fails**

Run: `pytest tests/auth/test_router.py -v`
Expected: FAIL (router/schemas/dependencies don't exist yet — collection error before Step 1-4 above are applied; if run after Steps 1-4 are already written, skip to Step 8)

- [ ] **Step 8: Run it to verify it passes**

Run: `pytest tests/auth/test_router.py -v` (requires `docker compose up -d postgres redis` and `cyberlearn_test` DB present from Task 1)
Expected: PASS (4 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/app/auth/schemas.py backend/app/auth/dependencies.py backend/app/auth/router.py backend/app/main.py backend/tests/conftest.py backend/tests/auth/__init__.py backend/tests/auth/test_router.py
git commit -m "feat: add login, MFA verify, me, and logout endpoints"
```

---

### Task 9: `create_owner.py` CLI script

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/create_owner.py`

**Interfaces:**
- Consumes: `app.db.SessionLocal` (Task 2), `app.models.user.User` (Task 3), `hash_password` (Task 4), `generate_totp_secret`/`totp_provisioning_uri` (Task 5).

- [ ] **Step 1: Write `backend/scripts/create_owner.py`**

```python
import argparse
import sys

from app.auth.security import hash_password
from app.auth.totp import generate_totp_secret, totp_provisioning_uri
from app.db import SessionLocal
from app.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the single OWNER user for CyberLearn.")
    parser.add_argument("username")
    parser.add_argument("password")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == args.username).first():
            print(f"User '{args.username}' already exists", file=sys.stderr)
            sys.exit(1)

        secret = generate_totp_secret()
        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            totp_secret=secret,
        )
        db.add(user)
        db.commit()

        print(f"Created user '{args.username}'")
        print(f"TOTP secret: {secret}")
        print(f"Add to your authenticator app: {totp_provisioning_uri(secret, args.username)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it against the dev database and verify**

Run:
```bash
cd backend
alembic upgrade head
python -m scripts.create_owner owner "a-strong-passphrase-1"
```
Expected: prints `Created user 'owner'`, a TOTP secret, and a `otpauth://` provisioning URI. Add that URI to an authenticator app (or decode manually) before Task 11's manual verification.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts
git commit -m "feat: add CLI script to create the OWNER user"
```

---

### Task 10: Frontend scaffold (React + Vite + Router)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: `api.login(username, password) -> Promise<{mfa_required: boolean}>`, `api.verifyMfa(code) -> Promise<{id, username}>`, `api.me() -> Promise<{id, username}>`, `api.logout() -> Promise<void>`, and `ApiError` (has `.status: number`) — consumed by Task 11.

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "cyberlearn-frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11"
  }
}
```

- [ ] **Step 2: Write `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

- [ ] **Step 3: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "skipLibCheck": true,
    "esModuleInterop": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Write `frontend/index.html`**

```html
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <title>CyberLearn</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `frontend/src/lib/api.ts`**

```typescript
const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });

  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ mfa_required: boolean }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  verifyMfa: (code: string) =>
    request<{ id: string; username: string }>("/auth/mfa/verify", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  me: () => request<{ id: string; username: string }>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
};
```

- [ ] **Step 6: Write a placeholder `frontend/src/main.tsx` and verify the dev server boots**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <h1>CyberLearn</h1>
  </StrictMode>
);
```

Run:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` — expect to see "CyberLearn" rendered.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/index.html frontend/src/main.tsx frontend/src/lib/api.ts
git commit -m "feat: scaffold React+Vite frontend with typed API client"
```

---

### Task 11: Login + MFA pages, auth context, protected routes

**Files:**
- Create: `frontend/src/features/auth/useAuth.tsx`
- Create: `frontend/src/features/auth/ProtectedRoute.tsx`
- Create: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/MfaPage.tsx`
- Create: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx` — render `<App />` instead of the placeholder

**Interfaces:**
- Consumes: `api` and `ApiError` from `frontend/src/lib/api.ts` (Task 10).
- Produces: `useAuth()` hook (`{user, loading, refresh}`), `<AuthProvider>`, `<ProtectedRoute>` — consumed by every future authenticated feature route in later sub-plans.

- [ ] **Step 1: Write `frontend/src/features/auth/useAuth.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, ApiError } from "../../lib/api";

type User = { id: string; username: string };

type AuthState = {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const me = await api.me();
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      } else {
        throw err;
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return <AuthContext.Provider value={{ user, loading, refresh }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Write `frontend/src/features/auth/ProtectedRoute.tsx`**

```tsx
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./useAuth";

export function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) return <p>Cargando…</p>;
  if (!user) return <Navigate to="/login" replace />;

  return <Outlet />;
}
```

- [ ] **Step 3: Write `frontend/src/features/auth/LoginPage.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const { mfa_required } = await api.login(username, password);
      if (mfa_required) {
        navigate("/mfa");
      }
    } catch {
      setError("Usuario o contraseña incorrectos");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h1>CyberLearn</h1>
      <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Usuario" />
      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        type="password"
        placeholder="Contraseña"
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit">Entrar</button>
    </form>
  );
}
```

- [ ] **Step 4: Write `frontend/src/features/auth/MfaPage.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "./useAuth";

export function MfaPage() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { refresh } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.verifyMfa(code);
      await refresh();
      navigate("/");
    } catch {
      setError("Código inválido");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h1>Verificación en dos pasos</h1>
      <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Código de 6 dígitos" />
      {error && <p role="alert">{error}</p>}
      <button type="submit">Verificar</button>
    </form>
  );
}
```

- [ ] **Step 5: Write `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./features/auth/useAuth";
import { LoginPage } from "./features/auth/LoginPage";
import { MfaPage } from "./features/auth/MfaPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";

function Home() {
  return <h1>Dashboard (placeholder)</h1>;
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/mfa" element={<MfaPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Home />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 6: Update `frontend/src/main.tsx` to render `App`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/auth frontend/src/App.tsx frontend/src/main.tsx
git commit -m "feat: add login/MFA pages, auth context, and protected routes"
```

---

### Task 12: End-to-end manual verification

**Files:** none (verification only).

- [ ] **Step 1: Bring up the full stack**

```bash
docker compose up -d postgres redis
cd backend && alembic upgrade head
```

- [ ] **Step 2: Create the OWNER user (if not already created in Task 9)**

```bash
python -m scripts.create_owner owner "a-strong-passphrase-1"
```
Note the TOTP secret / provisioning URI and add it to an authenticator app.

- [ ] **Step 3: Start backend and frontend**

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload
# terminal 2
cd frontend && npm run dev
```

- [ ] **Step 4: Walk the flow in a browser**

1. Open `http://localhost:5173` → redirected to `/login` (not authenticated yet).
2. Enter the OWNER username/password → redirected to `/mfa`.
3. Enter the current 6-digit code from the authenticator app → redirected to `/` showing "Dashboard (placeholder)".
4. Refresh the page → still on `/` (session persisted via cookie).
5. Manually call `POST /api/v1/auth/logout` (or add a temporary logout button) → refresh → redirected back to `/login`.

- [ ] **Step 5: Verify cookie security attributes**

In browser devtools → Application → Cookies, confirm the session cookie has `HttpOnly` checked and `SameSite=Strict`. (`Secure` will be off in local HTTP dev per `COOKIE_SECURE=false`; must be `true` when deployed behind HTTPS.)

- [ ] **Step 6: Run the full backend test suite one more time**

Run: `cd backend && pytest -v`
Expected: all tests from Tasks 4-8 pass.

No commit for this task — it's a verification checkpoint confirming Tasks 1-11 integrate correctly.
