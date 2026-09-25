from contextlib import nullcontext
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.database import Database
from app.infrastructure.passwords import hash_password, verify_password
from app.modules.audit.service import AuditService
from app.modules.users.repository import UsersRepository
from app.modules.users.schemas import UserIdentity, UserRecord


def _identity(user: UserRecord) -> UserIdentity:
    return UserIdentity(
        user_id=user.id,
        username=user.username,
        role=user.role,
        enabled=user.enabled,
        must_change_password=user.must_change_password,
        session_version=user.session_version,
    )


class UsersService:
    def __init__(self, database: Database):
        self._database = database

    def get_identity(self, user_id: UUID, *, transaction: Session | None = None) -> UserIdentity:
        with (
            nullcontext(transaction)
            if transaction is not None
            else self._database.transaction() as tx
        ):
            user = UsersRepository(tx).get(user_id)
            if user is None:
                raise ServiceError(ErrorCode.UNAUTHORIZED)
            return _identity(user)

    def authenticate(
        self, username: str, password: str, *, transaction: Session
    ) -> UserIdentity | None:
        user = UsersRepository(transaction).find_by_username(username, lock=True)
        valid = verify_password(user.password_hash if user else None, password)
        if not valid or user is None or not user.enabled:
            return None
        return _identity(user)

    def change_password(
        self, user_id: UUID, current_password: str, new_password: str, *, transaction: Session
    ) -> None:
        if not 12 <= len(new_password) <= 128 or current_password == new_password:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        repository = UsersRepository(transaction)
        user = repository.get(user_id, lock=True)
        if (
            user is None
            or not user.enabled
            or not verify_password(user.password_hash, current_password)
        ):
            raise ServiceError(ErrorCode.UNAUTHORIZED)
        repository.change_password(user_id, hash_password(new_password))

    def bootstrap_admin(self, username: str, password: str) -> UserIdentity:
        if not username or len(username) > 128 or not 12 <= len(password) <= 128:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        password_hash = hash_password(password)
        with self._database.transaction() as transaction:
            repository = UsersRepository(transaction)
            repository.lock_administration()
            if repository.administrator_count() or repository.find_by_username(username):
                raise ServiceError(ErrorCode.CONFLICT)
            user = repository.add(username=username, password_hash=password_hash, role="admin")
            AuditService().record(
                transaction=transaction,
                actor_id=user.id,
                action="admin.bootstrap",
                resource_id=user.id,
                outcome="succeeded",
                request_id=uuid4(),
            )
            return _identity(user)
