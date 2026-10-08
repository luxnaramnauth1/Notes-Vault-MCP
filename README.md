# Notes Vault MCP

A [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI assistants
(Claude Desktop, Claude Code, etc.) a persistent, searchable notebook backed by SQLite FTS5.

## Features

| Type | Name | Purpose |
|------|------|---------|
| Tool | `add_note`, `get_note`, `update_note`, `delete_note` | CRUD for notes |
| Tool | `list_notes` | Paginated listing, filter by tag |
| Tool | `search_notes` | Ranked full-text search with prefix matching |
| Tool | `tag_summary` | Tag usage counts |
| Resource | `notes://{id}`, `notes://tags` | Read notes as Markdown / tags as JSON |
| Prompt | `summarize_notes(tag)` | Summarise everything under a tag |

**Design notes**
- SQLite FTS5 index kept in sync via triggers (insert/update/delete).
- User search input is sanitised into safe FTS5 queries (no syntax errors from `C++` or quotes).
- Store logic is separated from the MCP layer, so it is unit-tested without a server.
- Tags are normalised (lowercase slugs, de-duplicated).

## Install

```bash
pip install -e ".[dev]"
pytest
```

## Use with Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notes-vault": {
      "command": "notes-vault-mcp",
      "env": { "NOTES_VAULT_DB": "~/.notes-vault/notes.db" }
    }
  }
}
```

## Use with Claude Code

```bash
claude mcp add notes-vault -- notes-vault-mcp
```

## Debug with the MCP Inspector

```bash
npx @modelcontextprotocol/inspector notes-vault-mcp
```

## Layout

```
src/notes_vault/store.py   # SQLite + FTS5 data layer
src/notes_vault/server.py  # MCP tools, resources, prompt
tests/test_store.py        # unit tests
```
