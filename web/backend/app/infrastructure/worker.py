"""Runner accepts composition callbacks; never imports business modules or the SDK."""

import logging
import threading
import time
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import text

WORKER_LOCK_ID = 4281092026
logger = logging.getLogger("batfish_web.worker")


@contextmanager
def worker_lease(database):
    with database.engine.connect() as connection:
        try:
            acquired = connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK_ID}
            )
            if not acquired:
                raise RuntimeError("Another worker is active")
            connection.commit()
            yield connection
        finally:
            # Do not return a potentially locked session to the pool, even after an uncertain reply.
            connection.invalidate()


class WorkerRunner:
    def __init__(self, database, service, settings):
        self.database, self.service, self.settings = database, service, settings
        self.worker_id = "worker-" + uuid4().hex
        self.stop = threading.Event()

    def run(self):
        with worker_lease(self.database) as lease:
            self.service.recover_stale()
            self.service.heartbeat(self.worker_id)
            pulse_stop = threading.Event()

            def heartbeat():
                while not pulse_stop.wait(self.settings.worker_heartbeat_seconds):
                    try:
                        lease.execute(text("SELECT 1"))
                        lease.commit()
                        self.service.heartbeat(self.worker_id)
                    except Exception as error:
                        logger.error("Heartbeat failed exception_type=%s", type(error).__name__)
                        self.service.stop_requested = True
                        self.stop.set()

            pulse = threading.Thread(target=heartbeat, name="worker-heartbeat", daemon=True)
            pulse.start()
            last_probe = 0
            try:
                while not self.stop.is_set() and not self.service.stop_requested:
                    if time.monotonic() - last_probe >= self.settings.engine_probe_seconds:
                        self.service.probe()
                        last_probe = time.monotonic()
                    if not self.service.run_once(self.worker_id):
                        self.stop.wait(self.settings.worker_poll_seconds)
            finally:
                self.stop.set()
                pulse_stop.set()
                pulse.join(timeout=max(1, self.settings.worker_heartbeat_seconds))
                self.service.heartbeat(self.worker_id, available=False)


def worker_is_stopped(transaction):
    """Hold the worker fence through a reconciliation transaction, preventing a late caller."""
    return bool(
        transaction.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": WORKER_LOCK_ID})
    )
