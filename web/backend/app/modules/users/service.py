from contextlib import nullcontext
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.database import Database
from app.infrastructure.passwords import hash_password, verify_password
from app.modules.audit.service import AuditService
from app.modules.users.repository import UsersRepository
from app.modules.users.schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UserDTO,
    UserIdentity,
    UserPage,
    UserRecord,
)


def _identity(user: UserRecord) -> UserIdentity:
    return UserIdentity(
        user_id=user.id,
        username=user.username,
        role=user.role,
        enabled=user.enabled,
        must_change_password=user.must_change_password,
        session_version=user.session_version,
    )


def _public(user: UserRecord) -> UserDTO:
    return UserDTO.model_validate({name: getattr(user, name) for name in UserDTO.model_fields})


class UsersService:
    def __init__(self, database: Database):
        self._database = database

    @staticmethod
    def _require_admin(repository: UsersRepository, actor: Actor) -> None:
        current = repository.get(actor.user_id)
        if (
            current is None
            or not current.enabled
            or current.role != "admin"
            or current.must_change_password
        ):
            raise ServiceError(ErrorCode.FORBIDDEN)

    def list(self, actor: Actor, *, offset: int = 0, limit: int = 50) -> UserPage:
        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as transaction:
            repository = UsersRepository(transaction)
            self._require_admin(repository, actor)
            users, total = repository.list(offset=offset, limit=limit)
            return UserPage(
                items=tuple(_public(user) for user in users),
                offset=offset,
                limit=limit,
                total=total,
            )

    def _manage(
        self, actor: Actor, *, action: str, resource_id: UUID | None, request_id: UUID, operation
    ):
        error = None
        result = None
        with self._database.transaction() as transaction:
            repository = UsersRepository(transaction)
            repository.lock_administration()
            try:
                self._require_admin(repository, actor)
                result = operation(repository)
            except ServiceError as failure:
                error = failure
            if repository.get(actor.user_id) is not None:
                AuditService().record(
                    transaction=transaction,
                    actor_id=actor.user_id,
                    action=action,
                    resource_id=resource_id or (result.id if result else None),
                    outcome="failed" if error else "succeeded",
                    request_id=request_id,
                )
        if error is not None:
            raise error
        return result

    def create(self, actor: Actor, request: CreateUserRequest, *, request_id: UUID) -> UserDTO:
        def operation(repository):
            if repository.find_by_username(request.username):
                raise ServiceError(ErrorCode.CONFLICT)
            return _public(
                repository.add(
                    username=request.username,
                    password_hash=hash_password(request.temporary_password.get_secret_value()),
                    role=request.role,
                )
            )

        return self._manage(
            actor,
            action="user.create",
            resource_id=None,
            request_id=request_id,
            operation=operation,
        )

    def update(
        self, actor: Actor, user_id: UUID, request: UpdateUserRequest, *, request_id: UUID
    ) -> UserDTO:
        def operation(repository):
            user = repository.get(user_id, lock=True)
            if user is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            enabled = user.enabled if request.enabled is None else request.enabled
            role = user.role if request.role is None else request.role
            if user.enabled and user.role == "admin" and (not enabled or role != "admin"):
                if repository.administrator_count(enabled_only=True) <= 1:
                    raise ServiceError(ErrorCode.CONFLICT)
            return _public(repository.update(user_id, enabled=request.enabled, role=request.role))

        return self._manage(
            actor,
            action="user.update",
            resource_id=user_id,
            request_id=request_id,
            operation=operation,
        )

    def reset_password(
        self, actor: Actor, user_id: UUID, temporary_password: str, *, request_id: UUID
    ) -> None:
        if not 12 <= len(temporary_password) <= 128:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)

        def operation(repository):
            if repository.get(user_id, lock=True) is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            repository.change_password(user_id, hash_password(temporary_password), temporary=True)

        self._manage(
            actor,
            action="user.password.reset",
            resource_id=user_id,
            request_id=request_id,
            operation=operation,
        )

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
