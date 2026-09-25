from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.users.schemas import UserRecord


def _record(user: User) -> UserRecord:
    return UserRecord(
        user.id,
        user.username,
        user.role,
        user.enabled,
        user.must_change_password,
        user.password_hash,
        user.session_version,
    )


class UsersRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def add(self, *, username: str, password_hash: str, role: str) -> UserRecord:
        user = User(username=username, password_hash=password_hash, role=role)
        self._transaction.add(user)
        self._transaction.flush()
        return _record(user)

    def get(self, user_id: UUID, *, lock: bool = False) -> UserRecord | None:
        query = select(User).where(User.id == user_id)
        user = self._transaction.scalar(query.with_for_update() if lock else query)
        return _record(user) if user else None

    def find_by_username(self, username: str, *, lock: bool = False) -> UserRecord | None:
        query = select(User).where(User.username == username)
        user = self._transaction.scalar(query.with_for_update() if lock else query)
        return _record(user) if user else None

    def lock_administration(self) -> None:
        self._transaction.execute(text("SELECT pg_advisory_xact_lock(4281042026)"))

    def administrator_count(self) -> int:
        return self._transaction.scalar(
            select(func.count()).select_from(User).where(User.role == "admin")
        )

    def change_password(self, user_id: UUID, password_hash: str) -> None:
        user = self._transaction.get(User, user_id)
        user.password_hash = password_hash
        user.must_change_password = False
        user.session_version += 1
        self._transaction.flush()
