"""Persistent memory: user facts (SQLite) + session conversation history.

  facts   — durable things Jen knows about the user (name, preferences,
            aliases). Persisted in SQLite across sessions.
  history — rolling conversation turns for context WITHIN a session only.
            Deliberately NOT persisted: replaying old turns poisoned the
            model (it learned refusals and text answers from them).

The store is thread-safe (the sidecar mutates config and runs TTS on
background threads) and works with ":memory:" for tests.
"""

import sqlite3
import threading
import time

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    updated_at REAL NOT NULL
);
"""

# Legacy table from builds that persisted conversation turns. Dropped on open
# so existing databases are cleaned automatically.
_LEGACY_HISTORY_DROP = "DROP TABLE IF EXISTS history"

MAX_HISTORY_ROWS = 200


def _normalize_key(key: str) -> str:
    return " ".join(str(key).strip().lower().split())


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        legacy = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
        ).fetchone()
        if legacy is not None:
            self._conn.execute(_LEGACY_HISTORY_DROP)
            self._conn.commit()
            self._conn.execute("VACUUM")
        self._conn.commit()
        self._turns: list[dict] = []

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- Facts (persisted) ---

    def add_fact(self, key: str, value: str, category: str = "general") -> str:
        key = _normalize_key(key)
        value = str(value).strip()
        if not key or not value:
            raise ValueError("fact key and value must be non-empty")
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO facts (key, value, category, updated_at) VALUES (?, ?, ?, ?)",
                (key, value, category, time.time()),
            )
            self._conn.commit()
        return key

    def remove_fact(self, key: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM facts WHERE key = ?", (_normalize_key(key),))
            self._conn.commit()
            return cur.rowcount > 0

    def facts(self) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM facts ORDER BY updated_at DESC"
            ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def clear_facts(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM facts")
            self._conn.commit()

    # --- History (session-only) ---

    def add_turn(self, role: str, content: str, tool_name: str | None = None) -> None:
        with self._lock:
            self._turns.append(
                {"role": role, "content": content, "tool_name": tool_name}
            )
            if len(self._turns) > MAX_HISTORY_ROWS:
                del self._turns[: len(self._turns) - MAX_HISTORY_ROWS]

    def recent_turns(self, limit: int = 12) -> list[dict]:
        with self._lock:
            return [dict(turn) for turn in self._turns[-limit:]]

    def clear_history(self) -> None:
        with self._lock:
            self._turns.clear()

    # --- Prompt assembly ---

    def context_block(self, max_facts: int = 20) -> str:
        """Compact 'About the user' block injected into the system prompt."""
        facts = self.facts()[:max_facts]
        if not facts:
            return ""
        lines = "\n".join(f"- {k}: {v}" for k, v in facts)
        return f"About the user:\n{lines}"
