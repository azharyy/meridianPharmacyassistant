"""Checks that this machine can run the project at all."""

import sqlite3


def test_sqlite_has_fts5() -> None:
    """Retrieval uses SQLite FTS5, so fail early on a Python built without it."""
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("create virtual table probe using fts5(text)")
    finally:
        connection.close()
