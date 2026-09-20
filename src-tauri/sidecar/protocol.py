"""JSON-lines protocol over stdout, consumed by the Rust host.

Every message is a single-line JSON object with a "status" field.
Stdout is reserved for protocol messages; logs go to stderr.
"""

import json
import sys
import threading

_lock = threading.Lock()


def emit(payload: dict) -> None:
    """Thread-safe single-line JSON emit to the host."""
    with _lock:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()
