"""MemoryStore: facts CRUD, rolling history, prompt block assembly."""


def test_facts_add_and_list(mem):
    mem.add_fact("name", "Sehaj")
    mem.add_fact("favorite editor", "VS Code")
    facts = dict(mem.facts())
    assert facts["name"] == "Sehaj"
    assert facts["favorite editor"] == "VS Code"


def test_facts_keys_normalized(mem):
    mem.add_fact("  Favorite   Editor ", "VS Code")
    assert ("favorite editor", "VS Code") in mem.facts()


def test_facts_upsert(mem):
    mem.add_fact("name", "Sehaj")
    mem.add_fact("name", "Sehajveer")
    assert dict(mem.facts())["name"] == "Sehajveer"
    assert len(mem.facts()) == 1


def test_facts_remove(mem):
    mem.add_fact("name", "Sehaj")
    assert mem.remove_fact("name") is True
    assert mem.remove_fact("name") is False
    assert mem.facts() == []


def test_facts_reject_empty(mem):
    import pytest

    with pytest.raises(ValueError):
        mem.add_fact("", "value")
    with pytest.raises(ValueError):
        mem.add_fact("key", "  ")


def test_history_order_and_limit(mem):
    mem.add_turn("user", "hello")
    mem.add_turn("assistant", "hi there")
    turns = mem.recent_turns(10)
    assert [t["role"] for t in turns] == ["user", "assistant"]
    assert turns[0]["content"] == "hello"


def test_history_prunes_to_rolling_window(mem):
    for i in range(250):
        mem.add_turn("user", f"turn {i}")
    turns = mem.recent_turns(300)
    assert len(turns) == 200
    assert turns[-1]["content"] == "turn 249"
    assert turns[0]["content"] == "turn 50"


def test_history_records_tool_names(mem):
    mem.add_turn("assistant", "[called open_app]", tool_name="open_app")
    assert mem.recent_turns(1)[0]["tool_name"] == "open_app"


def test_context_block_empty_without_facts(mem):
    assert mem.context_block() == ""


def test_context_block_contains_facts(mem):
    mem.add_fact("name", "Sehaj")
    mem.add_fact("music taste", "lo-fi")
    block = mem.context_block()
    assert "About the user:" in block
    assert "- name: Sehaj" in block
    assert "- music taste: lo-fi" in block


def test_persistence_roundtrip(tmp_path):
    from memory import MemoryStore

    db = str(tmp_path / "memory.db")
    m1 = MemoryStore(db)
    m1.add_fact("name", "Sehaj")
    m1.add_turn("user", "hello")
    m1.close()

    m2 = MemoryStore(db)
    assert dict(m2.facts())["name"] == "Sehaj"
    # History is session-only: it must NOT survive a restart
    assert m2.recent_turns(1) == []
    m2.close()


def test_legacy_history_table_is_purged_on_open(tmp_path):
    import sqlite3

    from memory import MemoryStore

    db = str(tmp_path / "memory.db")
    # Simulate a database from an older build that persisted turns
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "role TEXT NOT NULL, content TEXT NOT NULL, tool_name TEXT, created_at REAL NOT NULL)"
    )
    conn.execute(
        "INSERT INTO history (role, content, created_at) VALUES ('assistant', '[called open_app]', 0)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS facts (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "category TEXT NOT NULL DEFAULT 'general', updated_at REAL NOT NULL)"
    )
    conn.execute(
        "INSERT INTO facts (key, value, category, updated_at) VALUES ('editor', 'VS Code', 'general', 0)"
    )
    conn.commit()
    conn.close()

    store = MemoryStore(db)
    assert store.recent_turns(5) == []
    assert dict(store.facts())["editor"] == "VS Code"
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    assert "history" not in tables
    store.close()
