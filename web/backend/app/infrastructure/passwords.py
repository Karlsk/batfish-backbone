from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from argon2.low_level import Type

_hasher = PasswordHasher(type=Type.ID)
_dummy_hash = _hasher.hash("dummy credential used for unknown-user verification")


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Password length must be between 12 and 128 characters")
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        matched = _hasher.verify(password_hash or _dummy_hash, password)
    except VerificationError:
        return False
    return bool(password_hash and matched)
