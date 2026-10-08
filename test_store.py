import pytest

from notes_vault.store import NoteStore, normalize_tags


@pytest.fixture
def store():
    return NoteStore(":memory:")


def test_normalize_tags():
    assert normalize_tags(["Python", " python ", "Machine Learning", ""]) == "python,machine-learning"


def test_add_get_roundtrip(store):
    n = store.add("Hello", "World", ["A", "b"])
    assert store.get(n["id"])["tags"] == ["a", "b"]


def test_empty_title_rejected(store):
    with pytest.raises(ValueError):
        store.add("  ", "x")


def test_missing_note(store):
    with pytest.raises(KeyError):
        store.get(999)


def test_search_prefix_and_update_reindexes(store):
    n = store.add("Docker tips", "Use multistage builds", ["devops"])
    assert store.search("multi")[0]["id"] == n["id"]
    store.update(n["id"], body="Use compose instead")
    assert store.search("multistage") == []
    assert store.search("compose")[0]["id"] == n["id"]


def test_search_handles_special_characters(store):
    store.add("C++ notes", "pointers & references")
    assert store.search('c++ "pointers"')  # must not raise an FTS syntax error


def test_delete_removes_from_search(store):
    n = store.add("Temp", "ephemeral")
    store.delete(n["id"])
    assert store.search("ephemeral") == []


def test_list_by_tag_and_counts(store):
    store.add("1", "a", ["x", "y"])
    store.add("2", "b", ["x"])
    assert len(store.list(tag="x")) == 2
    assert len(store.list(tag="y")) == 1
    assert store.tag_counts() == {"x": 2, "y": 1}
