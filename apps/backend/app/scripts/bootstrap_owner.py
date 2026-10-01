"""Create the first owner without a committed/default credential.

Usage: ``uv run python -m app.scripts.bootstrap_owner owner@example.org``.
The password is read twice from the controlling terminal and never logged.
"""
import getpass
import sys
from uuid import uuid4

from sqlalchemy import func, select

from app.database import db
from app.models import User
from app.passwords import hash_password


def main() -> None:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        raise SystemExit("Usage: python -m app.scripts.bootstrap_owner EMAIL")
    password = getpass.getpass("Owner password (12+ characters): ")
    if len(password) < 12 or password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords must match and contain at least 12 characters")
    email = sys.argv[1].strip().lower()
    with db._sync_write_session() as session:
        if session.scalar(select(func.count()).select_from(User)):
            raise SystemExit("Bootstrap refused: a user already exists")
        session.add(User(user_id=str(uuid4()), email=email,
                         password_hash=hash_password(password), is_admin=True,
                         monthly_limit_cents=4000))
        session.commit()
    print(f"Owner created for {email}")


if __name__ == "__main__":
    main()
