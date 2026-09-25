from contextlib import contextmanager

from pybatfish.client.session import Session

from app.infrastructure.database import Database
from app.infrastructure.engine import EngineGate
from app.infrastructure.settings import Settings


class SessionFactory:
    def __init__(self, database: Database, settings: Settings):
        self._gate, self._settings = EngineGate(database), settings

    @contextmanager
    def exclusive(self, *, owner: str, load_questions: bool = False):
        with self._gate.exclusive(owner=owner):
            options = {
                "host": self._settings.batfish_host,
                "port": self._settings.batfish_port,
                "ssl": self._settings.batfish_tls,
                "timeout": self._settings.sdk_request_timeout,
                "load_questions": load_questions,
            }
            if self._settings.batfish_api_key is not None:
                options["api_key"] = self._settings.batfish_api_key.get_secret_value()
            # Public SDK has no close method; scope ends here and no session is cached.
            session = Session(**options)
            yield session
