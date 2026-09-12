import copy
import hashlib
import json
import sqlite3
import subprocess
import sys

import pytest

from argon_knowledge.semantic import search
from argon_knowledge.store import Conflict, KnowledgeError, Store, record_id
from argon_knowledge.transfer import export_markdown, markdown_import


def payload(body="Use private local knowledge.", scope="personal"):
    return dict(
        scope=scope,
        kind="fact",
        title="Local knowledge",
        body=body,
        source="test:source",
        source_revision="",
        tags=[],
        verification="reported",
        status="active",
    )


@pytest.fixture
def store(tmp_path):
    value = Store(tmp_path / "home/knowledge.sqlite3", create=True)
    yield value
    value.close()


def test_revision_conflicts_and_tombstones(store):
    key = record_id("personal", "a")
    first = store.put(key, payload())
    assert not store.put(key, payload())["changed"]
    with pytest.raises(Conflict):
        store.put(key, payload("Changed"))
    second = store.put(key, payload("Changed searchable unicorn"), first["revision"])
    assert store.get(key, first["revision"])["body"] == payload()["body"]
    assert len(store.history(key)) == 2
    assert store.lexical("unicorn")
    store.db.execute(
        "INSERT INTO embeddings VALUES(?,?,?)",
        (store.db.execute("SELECT id FROM chunks").fetchone()[0], "test", b"1234"),
    )
    store.set_status(key, "deleted", second["revision"])
    assert not store.lexical("unicorn")
    assert store.db.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 0


def test_scope_and_bounded_search(store):
    for scope in ["personal", "other"]:
        store.put(record_id(scope, "a"), payload("needle " * 500, scope))
    result = search(store, store.path.parent, "needle", "personal", "lexical")
    assert len(result["results"]) == 1
    assert result["results"][0]["scope"] == "personal"
    assert len(result["results"][0]["excerpt"]) <= 801
    assert not search(store, store.path.parent, "zzzzqx", mode="lexical")["results"]
    assert search(store, store.path.parent, "needle")["warnings"]


def test_import_export_and_protection(store, tmp_path):
    root = tmp_path / "notes"
    root.mkdir()
    original = "# Alpha\n\n[Beta](beta.md)\n<script>alert(1)</script>\n"
    (root / "alpha.md").write_text(original)
    (root / "beta.md").write_text("# Beta\n\nEvidence.")
    assert markdown_import(store, root, "notes", "personal")["changed"] == 2
    assert store.status()["records"] == 0
    markdown_import(store, root, "notes", "personal", apply=True)
    assert markdown_import(store, root, "notes", "personal", apply=True)["changed"] == 0
    output = export_markdown(store)
    from pathlib import Path

    path = Path(output["directory"])
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in (path / "index.html").read_text()
    alpha = path / "notes" / (record_id("personal", "notes:alpha.md") + ".md")
    assert record_id("personal", "notes:beta.md") + ".md" in alpha.read_text()
    assert (root / "alpha.md").read_text() == original
    for relative, expected in json.loads((path / "manifest.json").read_text())["files"].items():
        assert hashlib.sha256((path / relative).read_bytes()).hexdigest() == expected
    assert export_markdown(store) == output
    alpha.write_text("User edit")
    with pytest.raises(Conflict):
        export_markdown(store)
    (root / "alpha.md").write_text("# New content")
    with pytest.raises(Conflict):
        markdown_import(store, root, "notes", "personal", apply=True)


def test_merge_divergence_atomic_and_tampering(store, tmp_path):
    key = record_id("personal", "shared")
    initial = store.put(key, payload())
    other = Store(tmp_path / "other.sqlite3", create=True)
    try:
        bundle = store.bundle()
        assert other.merge(bundle)["records_to_update"] == 1
        assert other.status()["records"] == 0
        other.merge(bundle, apply=True)
        store.put(key, payload("remote change"), initial["revision"])
        other.merge(store.bundle(), apply=True)
        current = other.get(key)["revision"]
        other.put(key, payload("local fork"), current)
        store.put(key, payload("remote fork"), current)
        store.put(record_id("personal", "extra"), payload("Extra record"))
        with pytest.raises(Conflict):
            other.merge(store.bundle(), apply=True)
        assert other.status()["records"] == 1
        damaged = copy.deepcopy(bundle)
        damaged["revisions"][0]["payload"]["body"] = "tampered"
        with pytest.raises(KnowledgeError):
            other.merge(damaged, apply=True)
    finally:
        other.close()


def test_backup_and_secrets(store, tmp_path):
    store.put(record_id("personal", "a"), payload())
    target = tmp_path / "backup.sqlite3"
    store.backup(target)
    with sqlite3.connect(target) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 1
    with pytest.raises(KnowledgeError):
        store.put(record_id("personal", "secret"), payload("-----BEGIN PRIVATE KEY-----"))


def test_cli_lifecycle_and_bounded_get(tmp_path):
    base = [sys.executable, "-m", "argon_knowledge.cli", "--home", str(tmp_path / "cli")]

    def call(*args, data=None):
        return subprocess.run(
            base + list(args), input=data, text=True, capture_output=True, timeout=10
        )

    assert call("status").returncode == 2
    assert call("init").returncode == 0
    result = call(
        "put", "--key", "note", "--file", "-", data=json.dumps(payload("\n".join(["line"] * 250)))
    )
    assert result.returncode == 0, result.stderr
    key = json.loads(result.stdout)["id"]
    value = json.loads(call("get", key).stdout)
    assert value["total_lines"] == 250 and value["next_start_line"] == 81
    assert len(value["body"].splitlines()) == 80
    assert call("get", key, "--lines", "1000").returncode == 2
