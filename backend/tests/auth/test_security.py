from app.auth.security import hash_password, verify_password


def test_verify_password_correct():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False
