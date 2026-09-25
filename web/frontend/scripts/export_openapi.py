"""Generate the full contract without connecting to services or loading lab secrets."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.composition import create_app
from app.infrastructure.database import Database
from app.infrastructure.settings import Settings

database = Database('postgresql://openapi@127.0.0.1:1/openapi')
try:
    print(json.dumps(create_app(Settings(database_url=None), database=database).openapi()))
finally:
    database.close()
