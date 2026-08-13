import pyotp

from app.auth.totp import generate_totp_secret, verify_totp_code


def test_verify_totp_code_valid():
    secret = generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, code) is True


def test_verify_totp_code_invalid():
    secret = generate_totp_secret()
    assert verify_totp_code(secret, "000000") is False
