from uuid import UUID

from sqlalchemy import select
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
    )


class UsersRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def add(self, *, username: str, password_hash: str, role: str) -> UserRecord:
        user = User(username=username, password_hash=password_hash, role=role)
        self._transaction.add(user)
        self._transaction.flush()
        return _record(user)

    def get(self, user_id: UUID) -> UserRecord | None:
        user = self._transaction.get(User, user_id)
        return _record(user) if user else None

    def find_by_username(self, username: str) -> UserRecord | None:
        user = self._transaction.scalar(select(User).where(User.username == username))
        return _record(user) if user else None
