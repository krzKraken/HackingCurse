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
