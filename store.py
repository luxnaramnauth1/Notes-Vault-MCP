"""SQLite-backed note storage with FTS5 full-text search."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, body, tags, content='notes', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, body, tags)
    VALUES (new.id, new.title, new.body, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)
    VALUES ('delete', old.id, old.title, old.body, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)
    VALUES ('delete', old.id, old.title, old.body, old.tags);
    INSERT INTO notes_fts(rowid, title, body, tags)
    VALUES (new.id, new.title, new.body, new.tags);
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_tags(tags: list[str] | None) -> str:
    """Lowercase, dedupe and join tags as a comma-separated string."""
    seen: dict[str, None] = {}
    for t in tags or []:
        t = re.sub(r"[^a-z0-9_-]+", "-", t.strip().lower()).strip("-")
        if t:
            seen[t] = None
    return ",".join(seen)


def _fts_query(q: str) -> str:
    """Turn free text into a safe FTS5 query (prefix match on each term)."""
    terms = re.findall(r"\w+", q)
    if not terms:
        raise ValueError("Search query must contain at least one word.")
    return " ".join(f'"{t}"*' for t in terms)


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["tags"] = [t for t in d["tags"].split(",") if t]
    return d


class NoteStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path) if str(path) == ":memory:" else Path(path).expanduser())
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn:
            yield self._conn

    def add(self, title: str, body: str, tags: list[str] | None = None) -> dict:
        if not title.strip():
            raise ValueError("Title cannot be empty.")
        now = _now()
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO notes(title, body, tags, created_at, updated_at) VALUES (?,?,?,?,?)",
                (title.strip(), body, normalize_tags(tags), now, now),
            )
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, note_id: int) -> dict:
        r = self._conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if r is None:
            raise KeyError(f"No note with id {note_id}.")
        return _row(r)

    def update(self, note_id: int, title: str | None = None, body: str | None = None,
               tags: list[str] | None = None) -> dict:
        cur = self.get(note_id)
        with self._tx() as c:
            c.execute(
                "UPDATE notes SET title=?, body=?, tags=?, updated_at=? WHERE id=?",
                (
                    title.strip() if title else cur["title"],
                    body if body is not None else cur["body"],
                    normalize_tags(tags) if tags is not None else ",".join(cur["tags"]),
                    _now(),
                    note_id,
                ),
            )
        return self.get(note_id)

    def delete(self, note_id: int) -> None:
        self.get(note_id)
        with self._tx() as c:
            c.execute("DELETE FROM notes WHERE id=?", (note_id,))

    def list(self, tag: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
        limit = max(1, min(limit, 100))
        if tag:
            tag = normalize_tags([tag])
            rows = self._conn.execute(
                "SELECT * FROM notes WHERE ','||tags||',' LIKE ? ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                (f"%,{tag},%", limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM notes ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_row(r) for r in rows]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        limit = max(1, min(limit, 50))
        rows = self._conn.execute(
            """SELECT n.*, snippet(notes_fts, 1, '[', ']', '…', 12) AS snippet
               FROM notes_fts JOIN notes n ON n.id = notes_fts.rowid
               WHERE notes_fts MATCH ? ORDER BY rank LIMIT ?""",
            (_fts_query(query), limit),
        ).fetchall()
        return [_row(r) for r in rows]

    def tag_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._conn.execute("SELECT tags FROM notes"):
            for t in r["tags"].split(","):
                if t:
                    counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
