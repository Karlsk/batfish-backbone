"""Hold the owned lab worker at its documented pause boundary until stdin closes."""
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import lab  # noqa: E402


def stop(*_):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop)
with lab.exclusive_run(lab.RUNTIME / "operations.lock"), lab.paused_lab_worker():
    print("READY", flush=True)
    sys.stdin.readline()
