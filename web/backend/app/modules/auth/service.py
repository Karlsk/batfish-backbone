import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.database import Database
from app.infrastructure.settings import Settings
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import SessionInfo
from app.modules.users.service import UsersService


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class AuthService:
    def __init__(self, database: Database, users: UsersService, settings: Settings):
        self._database, self._users, self._settings = database, users, settings

    def require_origin(self, origin: str | None) -> None:
        if origin is None or origin not in self._settings.auth_allowed_origins:
            raise ServiceError(ErrorCode.FORBIDDEN)

    def login(
        self, username: str, password: str, *, origin: str | None, client_address: str
    ) -> tuple[SessionInfo, str]:
        self.require_origin(origin)
        keys = [_digest("login-pair:" + client_address + "\0" + username)]
        now = datetime.now(UTC)
        with self._database.transaction() as transaction:
            repository = AuthRepository(transaction)
            counts = repository.failure_counts(
                keys, now, self._settings.auth_failure_window_seconds
            )
            if max(counts) >= self._settings.auth_failure_limit:
                raise ServiceError(ErrorCode.RATE_LIMITED, retryable=True)
            identity = self._users.authenticate(username, password, transaction=transaction)
            if identity is None:
                repository.record_failure(keys)
            else:
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                repository.create(
                    user_id=identity.user_id,
                    session_version=identity.session_version,
                    token_hash=_digest(token),
                    csrf_secret=csrf,
                    expires_at=now + timedelta(hours=8),
                )
                info = SessionInfo(
                    user_id=identity.user_id,
                    username=identity.username,
                    role=identity.role,
                    must_change_password=identity.must_change_password,
                    csrf_token=csrf,
                )
        # Commit failed-attempt counters before reporting the uniform error.
        if identity is None:
            raise ServiceError(ErrorCode.UNAUTHORIZED)
        return info, token

    def _session(self, token: str | None, transaction: Session):
        if not token or len(token) != 43:
            raise ServiceError(ErrorCode.UNAUTHORIZED)
        session = AuthRepository(transaction).get(_digest(token))
        if session is None or session.revoked_at or session.expires_at <= datetime.now(UTC):
            raise ServiceError(ErrorCode.UNAUTHORIZED)
        identity = self._users.get_identity(session.user_id, transaction=transaction)
        if not identity.enabled or identity.session_version != session.session_version:
            raise ServiceError(ErrorCode.UNAUTHORIZED)
        return session, identity

    def require_actor(self, session_token: str | None) -> Actor:
        with self._database.transaction() as transaction:
            _, identity = self._session(session_token, transaction)
            if identity.must_change_password:
                raise ServiceError(ErrorCode.FORBIDDEN)
            return Actor(user_id=identity.user_id, role=identity.role, enabled=identity.enabled)

    def revalidate_actor(self, actor: Actor) -> Actor:
        identity = self._users.get_identity(actor.user_id)
        if not identity.enabled:
            raise ServiceError(ErrorCode.UNAUTHORIZED)
        if identity.must_change_password:
            raise ServiceError(ErrorCode.FORBIDDEN)
        return Actor(user_id=identity.user_id, role=identity.role, enabled=True)

    def me(self, session_token: str | None) -> SessionInfo:
        with self._database.transaction() as transaction:
            session, identity = self._session(session_token, transaction)
            return SessionInfo(
                user_id=identity.user_id,
                username=identity.username,
                role=identity.role,
                must_change_password=identity.must_change_password,
                csrf_token=session.csrf_secret,
            )

    def require_write(
        self, session_token: str | None, *, origin: str | None, csrf_token: str | None
    ) -> Actor:
        self.require_origin(origin)
        with self._database.transaction() as transaction:
            session, identity = self._session(session_token, transaction)
            self._check_csrf(session.csrf_secret, csrf_token)
            if identity.must_change_password:
                raise ServiceError(ErrorCode.FORBIDDEN)
            return Actor(user_id=identity.user_id, role=identity.role, enabled=identity.enabled)

    @staticmethod
    def _check_csrf(secret: str, provided: str | None) -> None:
        if not provided or not secrets.compare_digest(secret.encode(), provided.encode()):
            raise ServiceError(ErrorCode.FORBIDDEN)

    def logout(
        self, session_token: str | None, *, origin: str | None, csrf_token: str | None
    ) -> None:
        self.require_origin(origin)
        with self._database.transaction() as transaction:
            session, _ = self._session(session_token, transaction)
            self._check_csrf(session.csrf_secret, csrf_token)
            AuthRepository(transaction).revoke(_digest(session_token), datetime.now(UTC))

    def change_password(
        self,
        session_token: str | None,
        current_password: str,
        new_password: str,
        *,
        origin: str | None,
        csrf_token: str | None,
    ) -> None:
        self.require_origin(origin)
        with self._database.transaction() as transaction:
            session, identity = self._session(session_token, transaction)
            self._check_csrf(session.csrf_secret, csrf_token)
            self._users.change_password(
                identity.user_id, current_password, new_password, transaction=transaction
            )
            AuthRepository(transaction).revoke_user(identity.user_id, datetime.now(UTC))
