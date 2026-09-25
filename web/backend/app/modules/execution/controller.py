from app.infrastructure.engine import EngineBusy
from app.infrastructure.sdk import SessionFactory


class ExecutionController:
    def __init__(self, database, settings):
        self._sessions = SessionFactory(database, settings)

    def probe(self):
        try:
            with self._sessions.exclusive(owner="worker-health") as session:
                try:
                    return bool(session.get_component_versions().get("Batfish"))
                except Exception:
                    # Read-only health failure is no evidence of an in-flight remote mutation.
                    return False
        except EngineBusy:
            return None
