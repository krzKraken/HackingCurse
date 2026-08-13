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
