from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthSession, LoginAttempt
from app.modules.auth.schemas import SessionRecord


class AuthRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def create(
        self,
        *,
        user_id: UUID,
        session_version: int,
        token_hash: str,
        csrf_secret: str,
        expires_at: datetime,
    ) -> None:
        self._transaction.add(
            AuthSession(
                user_id=user_id,
                session_version=session_version,
                token_hash=token_hash,
                csrf_secret=csrf_secret,
                expires_at=expires_at,
            )
        )
        self._transaction.flush()

    def get(self, token_hash: str) -> SessionRecord | None:
        row = self._transaction.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )
        return (
            SessionRecord(
                row.user_id, row.session_version, row.expires_at, row.revoked_at, row.csrf_secret
            )
            if row
            else None
        )

    def revoke(self, token_hash: str, now: datetime) -> None:
        self._transaction.execute(
            update(AuthSession).where(AuthSession.token_hash == token_hash).values(revoked_at=now)
        )

    def revoke_user(self, user_id: UUID, now: datetime) -> None:
        self._transaction.execute(
            update(AuthSession).where(AuthSession.user_id == user_id).values(revoked_at=now)
        )

    def failure_counts(self, keys: list[str], now: datetime, window_seconds: int) -> list[int]:
        counts = []
        for key in sorted(keys):
            # Transaction-scoped locks serialize checks and updates across API processes.
            lock_id = int.from_bytes(bytes.fromhex(key)[:8], "big", signed=True)
            self._transaction.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
            self._transaction.execute(
                insert(LoginAttempt)
                .values(key=key, window_start=now, failures=0)
                .on_conflict_do_nothing()
            )
            row = self._transaction.get(LoginAttempt, key)
            if row.window_start + timedelta(seconds=window_seconds) <= now:
                row.window_start, row.failures = now, 0
            counts.append(row.failures)
        return counts

    def record_failure(self, keys: list[str]) -> None:
        for key in keys:
            self._transaction.get(LoginAttempt, key).failures += 1
        self._transaction.flush()
