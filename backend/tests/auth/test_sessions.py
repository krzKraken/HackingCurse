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
