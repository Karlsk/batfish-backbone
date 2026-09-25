"""Use DATABASE_URL at runtime; never put credentials in alembic.ini or logs."""

import os

from alembic import context

from app.composition import database_metadata
from app.infrastructure.database import Database

metadata = database_metadata()


def migrate(connection):
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(dialect_name="postgresql", target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    migrate(context.config.attributes["connection"])
else:
    database = Database(os.environ["DATABASE_URL"])
    try:
        with database.engine.connect() as connection:
            migrate(connection)
    finally:
        database.close()
