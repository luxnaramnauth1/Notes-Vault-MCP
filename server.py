"""MCP server exposing the note store as tools, resources and a prompt."""
from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from .store import NoteStore

mcp = FastMCP("notes-vault")

_store: NoteStore | None = None


def get_store() -> NoteStore:
    """Lazily open the DB (path from NOTES_VAULT_DB, default ~/.notes-vault/notes.db)."""
    global _store
    if _store is None:
        _store = NoteStore(os.environ.get("NOTES_VAULT_DB", "~/.notes-vault/notes.db"))
    return _store


# ---------------------------------------------------------------- tools
@mcp.tool()
def add_note(title: str, body: str, tags: list[str] | None = None) -> dict:
    """Create a note. Tags are normalised to lowercase slugs."""
    return get_store().add(title, body, tags)


@mcp.tool()
def get_note(note_id: int) -> dict:
    """Fetch a single note by id."""
    return get_store().get(note_id)


@mcp.tool()
def update_note(note_id: int, title: str | None = None, body: str | None = None,
                tags: list[str] | None = None) -> dict:
    """Update any of title, body or tags. Omitted fields are left unchanged."""
    return get_store().update(note_id, title, body, tags)


@mcp.tool()
def delete_note(note_id: int) -> str:
    """Permanently delete a note."""
    get_store().delete(note_id)
    return f"Deleted note {note_id}."


@mcp.tool()
def list_notes(tag: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    """List notes, newest first, optionally filtered by tag."""
    return get_store().list(tag, limit, offset)


@mcp.tool()
def search_notes(query: str, limit: int = 10) -> list[dict]:
    """Full-text search across title, body and tags (prefix matching, ranked)."""
    return get_store().search(query, limit)


@mcp.tool()
def tag_summary() -> dict[str, int]:
    """Return every tag with the number of notes using it."""
    return get_store().tag_counts()


# ------------------------------------------------------------ resources
@mcp.resource("notes://tags")
def tags_resource() -> str:
    """All tags and their counts as JSON."""
    return json.dumps(get_store().tag_counts(), indent=2)


@mcp.resource("notes://{note_id}")
def note_resource(note_id: int) -> str:
    """A single note rendered as Markdown."""
    n = get_store().get(note_id)
    tags = ", ".join(n["tags"]) or "none"
    return f"# {n['title']}\n\n*Tags: {tags} · Updated {n['updated_at']}*\n\n{n['body']}\n"


# --------------------------------------------------------------- prompt
@mcp.prompt()
def summarize_notes(tag: str) -> str:
    """Ask the model to summarise every note under a tag."""
    notes = get_store().list(tag, limit=100)
    if not notes:
        return f"There are no notes tagged '{tag}'. Tell the user that."
    joined = "\n\n".join(f"## {n['title']}\n{n['body']}" for n in notes)
    return (f"Summarise the following {len(notes)} notes tagged '{tag}'. "
            f"Group related ideas and list any action items.\n\n{joined}")


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
