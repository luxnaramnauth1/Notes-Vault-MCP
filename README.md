# Notes Vault MCP

A **Model Context Protocol (MCP) server** that gives AI assistants such as Claude a persistent, searchable notebook. Notes are stored locally in SQLite and searched with full-text search (FTS5).

Built with **Python**, the **official MCP SDK**, and **SQLite**. Includes unit tests and works over stdio with Claude Desktop and Claude Code.

---

## What problem does it solve?

AI assistants forget everything between conversations. Notes Vault gives them a small, local memory they can read and write through a standard protocol:

- "Save a note about the Docker tips we just discussed."
- "Search my notes for anything about authentication."
- "Summarise everything I've tagged `project-ideas`."

Your data stays on your machine in a single SQLite file. Nothing is sent to a third-party service.

---

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard that lets AI applications connect to external tools and data in a uniform way. An MCP server can expose three kinds of things:

| Concept | Meaning | Controlled by |
|---------|---------|---------------|
| **Tools** | Actions the model can call (add a note, search) | The model |
| **Resources** | Read-only data the app can load into context | The application |
| **Prompts** | Reusable prompt templates | The user |

This project uses all three.

---

## Features

### Tools

| Tool | Description |
|------|-------------|
| `add_note(title, body, tags?)` | Create a note |
| `get_note(note_id)` | Fetch one note |
| `update_note(note_id, title?, body?, tags?)` | Change any field; others are left as-is |
| `delete_note(note_id)` | Permanently delete a note |
| `list_notes(tag?, limit?, offset?)` | Newest first, with pagination and tag filter |
| `search_notes(query, limit?)` | Ranked full-text search with prefix matching and highlighted snippets |
| `tag_summary()` | Every tag with how many notes use it |

### Resources

| URI | Returns |
|-----|---------|
| `notes://{id}` | A single note rendered as Markdown |
| `notes://tags` | All tags and counts as JSON |

### Prompt

| Name | Purpose |
|------|---------|
| `summarize_notes(tag)` | Gathers every note under a tag and asks the model to group ideas and list action items |

---

## How it works

```
 ┌──────────────────┐   stdio / JSON-RPC   ┌──────────────────────────┐
 │ Claude Desktop   │ ───────────────────▶ │  server.py               │
 │ Claude Code      │ ◀─────────────────── │  (tools, resources,      │
 │ any MCP client   │                      │   prompt definitions)    │
 └──────────────────┘                      └────────────┬─────────────┘
                                                        │ calls
                                           ┌────────────▼─────────────┐
                                           │  store.py                │
                                           │  NoteStore (SQLite+FTS5) │
                                           └────────────┬─────────────┘
                                                        │
                                              ~/.notes-vault/notes.db
```

1. The MCP client launches the server as a subprocess and talks to it over **stdio** using JSON-RPC.
2. `server.py` declares tools, resources and the prompt using the SDK's `FastMCP` decorators.
3. Each handler delegates to `NoteStore` in `store.py`, which owns all database logic.

### Design decisions

- **Separation of concerns.** Data logic lives in `store.py` with no MCP imports, so it can be unit-tested directly without starting a server.
- **FTS5 kept in sync by triggers.** Insert, update and delete triggers update the search index automatically, so the index can't drift from the notes table.
- **Safe search input.** Raw user text can break FTS5 syntax (for example `C++` or stray quotes). Queries are tokenised and each term is quoted with a prefix wildcard, so any input is handled safely.
- **Tag normalisation.** Tags are lowercased, converted to slugs and de-duplicated, so `Python`, `python ` and `PYTHON` are the same tag.
- **Input limits.** `limit` values are clamped (max 100 for listing, 50 for search) to protect against huge responses.
- **Lazy database connection.** The database opens on first use, and its location is configurable via an environment variable.

---

## Project structure

```
notes-vault-mcp/
├── pyproject.toml            # packaging, dependencies, console script
├── README.md
├── src/notes_vault/
│   ├── __init__.py
│   ├── __main__.py           # enables `python -m notes_vault`
│   ├── server.py             # MCP tools, resources, prompt
│   └── store.py              # SQLite + FTS5 data layer
└── tests/
    └── test_store.py         # unit tests for the data layer
```

---

## Installation

Requires **Python 3.10+**.

```bash
git clone <your-repo-url>
cd notes-vault-mcp
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the tests:

```bash
pytest
```

---

## Connecting it to a client

### Claude Desktop

Add this to `claude_desktop_config.json`, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "notes-vault": {
      "command": "/full/path/to/.venv/bin/notes-vault-mcp",
      "env": { "NOTES_VAULT_DB": "~/.notes-vault/notes.db" }
    }
  }
}
```

### Claude Code

```bash
claude mcp add notes-vault -- /full/path/to/.venv/bin/notes-vault-mcp
```

### MCP Inspector (for debugging)

```bash
npx @modelcontextprotocol/inspector /full/path/to/.venv/bin/notes-vault-mcp
```

---

## Example conversation

> **You:** Save a note titled "Postgres indexing" saying that partial indexes help with soft-deleted rows. Tag it `database` and `postgres`.
>
> **Claude:** *(calls `add_note`)* Saved as note #1.
>
> **You:** What did I write about indexes?
>
> **Claude:** *(calls `search_notes` with `index`)* You have one note, "Postgres indexing", which says partial indexes help with soft-deleted rows.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTES_VAULT_DB` | `~/.notes-vault/notes.db` | Path to the SQLite database file |

---

## Testing

The test suite covers:

- Tag normalisation and de-duplication
- Create / read round trips
- Validation errors (empty title, missing note)
- Prefix search and index updates after edits
- Search with special characters (no FTS syntax errors)
- Deletion removing notes from search results
- Tag filtering and tag counts

The server was also verified end to end with a real MCP client over stdio (listing tools, calling tools, reading a resource, and fetching the prompt).

---

## Tech stack

- Python 3.10+
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`mcp>=1.2,<2`)
- SQLite with FTS5
- pytest

> **Note:** the SDK is pinned below 2.0 because version 2 renamed `FastMCP`. Upgrading would require a small migration.

---

## Possible extensions

- Semantic search using embeddings alongside FTS5
- Export / import notes as Markdown files
- Streamable HTTP transport for remote use
- Note linking and backlinks
- Authentication for multi-user deployments

---

## License

MIT
