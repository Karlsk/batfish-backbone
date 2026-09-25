from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent


def record(transaction: Session, **fields) -> None:
    transaction.add(AuditEvent(**fields))
    transaction.flush()
