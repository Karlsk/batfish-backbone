from app.infrastructure.database import Database
from app.infrastructure.engine import EngineBusy, EngineOutcomeUnknown
from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from app.modules.networks.schemas import NetworkUnavailable


class NetworkController:
    def __init__(self, database: Database, settings: Settings):
        self._sessions = SessionFactory(database, settings)

    def create(self, engine_name: str) -> None:
        try:
            with self._sessions.exclusive(owner=engine_name) as session:
                if session.set_network(engine_name) != engine_name:
                    raise ValueError("Unexpected SDK network identity")
        except EngineBusy as error:
            raise NetworkUnavailable("ENGINE_UNKNOWN" if error.unknown else "ENGINE_BUSY") from None
        except EngineOutcomeUnknown:
            raise NetworkUnavailable("ENGINE_UNKNOWN", failed=True) from None
        except Exception:
            raise NetworkUnavailable("ENGINE_UNAVAILABLE", failed=True) from None

    def deletion_presence(self, engine_name, *, remove=False):
        with self._sessions.exclusive(owner=engine_name) as session:
            exists = engine_name in session.list_networks()
            if remove and exists:
                session.delete_network(engine_name)
                exists = engine_name in session.list_networks()
                if exists:
                    raise RuntimeError("Remote deletion is not confirmed")
            return exists
