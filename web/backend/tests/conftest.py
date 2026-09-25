import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.infrastructure.database import Database


@pytest.fixture
def database():
    manifest_path = os.environ.get("BATFISH_LAB_MANIFEST")
    assert manifest_path, "Use web/scripts/lab.py verify for isolated PostgreSQL tests"
    manifest = json.loads(Path(manifest_path).read_text())
    assert manifest["isolated"] is True and manifest["host"] == "127.0.0.1"
    secret = Path(manifest["run_directory"]) / "database.env"
    url = secret.read_text().strip().removeprefix("DATABASE_URL=")
    schema = "test_" + uuid4().hex
    admin = Database(url)
    with admin.engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    db = Database(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield db
    finally:
        db.close()
        with admin.engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.close()
