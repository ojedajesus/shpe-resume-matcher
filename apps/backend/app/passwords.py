"""Versioned, memory-hard password hashing using cryptography's Scrypt."""
import base64
import secrets

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())
    return "scrypt$32768$8$1$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(derived).decode()


def verify_password(encoded: str, password: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        Scrypt(salt=base64.urlsafe_b64decode(salt), length=32, n=int(n), r=int(r), p=int(p)).verify(
            password.encode(), base64.urlsafe_b64decode(expected))
        return True
    except (ValueError, InvalidKey):
        return False
