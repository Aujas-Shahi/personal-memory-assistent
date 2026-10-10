"""
SQLite-backed tag store.

Schema
------
tags        (id INTEGER PK, name TEXT UNIQUE, parent_id INTEGER nullable, color TEXT)
file_tags   (file_path TEXT, tag_id INTEGER, auto_tagged INTEGER, PRIMARY KEY(file_path, tag_id))
"""

from __future__ import annotations

import sqlite3
import os
from typing import Optional

from config.settings import TAGS_DB_PATH as DB_PATH


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tags (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL UNIQUE,
                parent_id INTEGER,
                color     TEXT    DEFAULT '#888888'
            );

            CREATE TABLE IF NOT EXISTS file_tags (
                file_path  TEXT    NOT NULL,
                tag_id     INTEGER NOT NULL,
                auto_tagged INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (file_path, tag_id),
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );
        """)


def _get_or_create_tag(conn: sqlite3.Connection, name: str, parent_name: Optional[str] = None) -> int:
    """Return tag id, creating it (and its parent) if needed."""
    parent_id = None
    if parent_name:
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (parent_name,)).fetchone()
        if row:
            parent_id = row["id"]
        else:
            conn.execute(
                "INSERT OR IGNORE INTO tags (name) VALUES (?)", (parent_name,)
            )
            parent_id = conn.execute(
                "SELECT id FROM tags WHERE name = ?", (parent_name,)
            ).fetchone()["id"]

    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]

    conn.execute(
        "INSERT OR IGNORE INTO tags (name, parent_id) VALUES (?, ?)",
        (name, parent_id),
    )
    return conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()["id"]


def set_file_tags(
    file_path: str,
    tag_names: list[str],
    auto_tagged: bool = True,
    parent_map: Optional[dict[str, str]] = None,
):
    """
    Replace all auto-tagged (or all manual) tags for a file with the given list.
    parent_map: {tag_name: parent_tag_name}
    """
    init_db()
    parent_map = parent_map or {}
    flag = 1 if auto_tagged else 0

    with _connect() as conn:
        # Remove existing tags of this type for the file.
        conn.execute(
            "DELETE FROM file_tags WHERE file_path = ? AND auto_tagged = ?",
            (file_path, flag),
        )

        for name in tag_names:
            parent = parent_map.get(name)
            tag_id = _get_or_create_tag(conn, name, parent)
            conn.execute(
                "INSERT OR IGNORE INTO file_tags (file_path, tag_id, auto_tagged) VALUES (?, ?, ?)",
                (file_path, tag_id, flag),
            )


def get_file_tags(file_path: str) -> list[dict]:
    """Return all tags (auto + manual) for a file."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.color, t.parent_id, ft.auto_tagged,
                   p.name AS parent_name
            FROM file_tags ft
            JOIN tags t ON ft.tag_id = t.id
            LEFT JOIN tags p ON t.parent_id = p.id
            WHERE ft.file_path = ?
            ORDER BY ft.auto_tagged DESC, t.name ASC
            """,
            (file_path,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_manual_tag(file_path: str, tag_name: str, parent_name: Optional[str] = None):
    """Add a single manual tag to a file."""
    init_db()
    with _connect() as conn:
        tag_id = _get_or_create_tag(conn, tag_name, parent_name)
        conn.execute(
            "INSERT OR IGNORE INTO file_tags (file_path, tag_id, auto_tagged) VALUES (?, ?, 0)",
            (file_path, tag_id),
        )


def remove_tag_from_file(file_path: str, tag_name: str):
    """Remove a specific tag from a file."""
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
        if row:
            conn.execute(
                "DELETE FROM file_tags WHERE file_path = ? AND tag_id = ?",
                (file_path, row["id"]),
            )


def get_all_tags() -> list[dict]:
    """Return all tags with parent info and file counts."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.color, t.parent_id, p.name AS parent_name,
                   COUNT(ft.file_path) AS file_count
            FROM tags t
            LEFT JOIN tags p ON t.parent_id = p.id
            LEFT JOIN file_tags ft ON ft.tag_id = t.id
            GROUP BY t.id
            ORDER BY t.name ASC
            """,
        ).fetchall()
    return [dict(r) for r in rows]


def get_files_by_tag(tag_name: str) -> list[str]:
    """Return file paths that have this tag (or any child tag)."""
    init_db()
    with _connect() as conn:
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
        if not tag_row:
            return []

        tag_id = tag_row["id"]

        # Include direct matches and any tags whose parent matches.
        rows = conn.execute(
            """
            SELECT DISTINCT ft.file_path
            FROM file_tags ft
            JOIN tags t ON ft.tag_id = t.id
            WHERE t.id = ? OR t.parent_id = ?
            """,
            (tag_id, tag_id),
        ).fetchall()

    return [r["file_path"] for r in rows]


def clear_all_file_tags():
    """Remove every file-tag association (used when the index is reset)."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM file_tags")


def delete_file_tags(file_path: str):
    """Remove all tag associations for a file (e.g. when file is deleted)."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM file_tags WHERE file_path = ?", (file_path,))
