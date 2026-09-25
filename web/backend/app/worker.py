import signal

from app.composition import create_worker
from app.infrastructure.settings import Settings


def main():
    runner = create_worker(Settings())
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_args: runner.stop.set())
    try:
        runner.run()
    finally:
        runner.database.close()


if __name__ == "__main__":
    main()
