"""Shared pytest fixtures: make the sidecar package importable.

The sidecar modules use flat sibling imports (main.py is a PyInstaller
entry script), so tests add src-tauri/sidecar to sys.path.
"""

import os
import sys

import pytest

SIDECAR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src-tauri", "sidecar"))
if SIDECAR_DIR not in sys.path:
    sys.path.insert(0, SIDECAR_DIR)

from config import SidecarConfig  # noqa: E402
from memory import MemoryStore  # noqa: E402


@pytest.fixture
def cfg():
    return SidecarConfig()


@pytest.fixture
def mem():
    m = MemoryStore(":memory:")
    yield m
    m.close()


@pytest.fixture
def captured_events():
    """Collect protocol events instead of emitting them."""
    return []
