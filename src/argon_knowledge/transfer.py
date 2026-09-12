from __future__ import annotations

import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import tempfile
from pathlib import Path

from .store import FIELDS, Conflict, KnowledgeError, canonical, digest, record_id, validate_payload


def read_json(path, maximum=25_000_000):
    p = Path(path)
    if p.stat().st_size > maximum:
        raise KnowledgeError("Input file exceeds the size limit.")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def write_new_json(path, value):
    p = Path(path).expanduser().absolute()
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with p.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
    return str(p)


def markdown_import(store, root, namespace, scope, source_revision="", apply=False, update=False):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir() or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", namespace):
        raise KnowledgeError("Import requires a directory and a simple source namespace.")
    entries = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if path.is_symlink() or path.resolve().is_relative_to(root) is False:
            raise KnowledgeError("Import symlinks are not supported.")
        if path.stat().st_size > 500_000:
            raise KnowledgeError("Markdown input exceeds the per-record limit: " + str(rel))
        body = path.read_text(encoding="utf-8-sig")
        if not body.strip():
            continue
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        payload = {
            "scope": scope,
            "kind": "reference",
            "title": heading.group(1)[:300] if heading else path.stem,
            "body": body,
            "source": namespace + ":" + rel.as_posix(),
            "source_revision": source_revision,
            "verification": "unverified",
            "tags": ["imported"],
            "status": "active",
        }
        validate_payload(payload)
        identifier = record_id(scope, payload["source"])
        entries.append((identifier, payload))
    results = []
    with store.transaction():
        for identifier, payload in entries:
            row = store.db.execute("SELECT head FROM records WHERE id=?", (identifier,)).fetchone()
            expected = row["head"] if row else None
            current = store.get(identifier) if row else None
            changed = current is None or canonical({k: current[k] for k in FIELDS}) != canonical(
                payload
            )
            if row and changed and not update:
                raise Conflict(
                    "Imported record changed; review it and explicitly use --update to replace it."
                )
            if apply:
                store.put(identifier, payload, expected)
            results.append({"id": identifier, "source": payload["source"], "changed": changed})
    return {
        "apply": apply,
        "records": len(entries),
        "changed": sum(x["changed"] for x in results),
        "items": results,
    }


def export_markdown(store, output=None):
    # Read one consistent snapshot, then release the DB lock before filesystem work.
    with store.transaction():
        records = [store.get(row["id"]) for row in store.list_records()]
        heads = {r["id"]: r["revision"] for r in store.list_records(include_inactive=True)}
    snapshot = digest(heads)[:20]
    root = (
        Path(output).expanduser().absolute() if output else store.path.parent / "exports" / snapshot
    )
    source_map = {r["source"]: r["id"] for r in records}
    generated = {}
    index = [
        "# Knowledge export",
        "",
        "Generated from the knowledge store. Edit records through the tool.",
        "",
        f"Snapshot: `{snapshot}`",
        "",
    ]
    cards = []
    for record in records:
        body = record["body"]
        source = record["source"]
        if ":" in source:
            namespace, relative = source.split(":", 1)

            def replace(match):
                target = match.group(2)
                if ":" in target or target.startswith(("/", "#")):
                    return match.group(0)
                path, _, anchor = target.partition("#")
                resolved = (
                    namespace
                    + ":"
                    + posixpath.normpath(posixpath.join(posixpath.dirname(relative), path))
                )
                if resolved not in source_map:
                    return match.group(0)
                return (
                    "["
                    + match.group(1)
                    + "]("
                    + source_map[resolved]
                    + ".md"
                    + ("#" + anchor if anchor else "")
                    + ")"
                )

            body = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace, body)
        meta = {
            k: record[k]
            for k in [
                "id",
                "revision",
                "scope",
                "kind",
                "source",
                "source_revision",
                "verification",
                "recorded_at",
            ]
        }
        front = "\n".join(k + ": " + json.dumps(v, ensure_ascii=False) for k, v in meta.items())
        generated["notes/" + record["id"] + ".md"] = (
            "---\n" + front + "\n---\n\n" + body.rstrip() + "\n"
        )
        label = record["title"].replace("[", "").replace("]", "").replace("\n", " ")
        index.append(
            f"- [{label}](notes/{record['id']}.md) — {record['scope']} · {record['verification']}"
        )
        cards.append(
            "<article><h2>"
            + html.escape(record["title"])
            + '</h2><p class="meta">'
            + html.escape(record["scope"] + " · " + record["kind"] + " · " + record["verification"])
            + "</p><details><summary>Read record</summary><pre>"
            + html.escape(body)
            + "</pre></details>"
            + '<p class="meta">Source: '
            + html.escape(record["source"])
            + " · Revision: "
            + record["revision"][:12]
            + "</p></article>"
        )
    generated["index.md"] = "\n".join(index) + "\n"
    generated["index.html"] = (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Personal knowledge</title><style>
body{max-width:1000px;margin:48px auto;padding:0 24px;font:16px/1.6 system-ui;background:#f5f4ef;color:#183029}h1{font-size:40px;letter-spacing:-1px}article{background:white;border:1px solid #d8ded8;border-radius:12px;padding:22px;margin:18px 0}h2{margin:0;font-size:21px}.meta{color:#577069;font-size:13px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace}input{width:100%;box-sizing:border-box;padding:14px;border:1px solid #9aaa9f;border-radius:8px;font:inherit}summary{cursor:pointer;color:#216952}
</style><h1>Personal knowledge</h1><p>Private, human-readable snapshot. Changes belong in the knowledge tool.</p><input id="filter" placeholder="Filter records on this page" aria-label="Filter records">"""
        + "".join(cards)
        + """<script>
document.getElementById('filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q))});
</script></html>"""
    )
    hashes = {name: hashlib.sha256(data.encode()).hexdigest() for name, data in generated.items()}
    generated["manifest.json"] = (
        canonical({"format": "argon-knowledge-export/v1", "snapshot": snapshot, "files": hashes})
        + "\n"
    )
    if root.exists():
        actual = {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }
        expected = {n: hashlib.sha256(v.encode()).hexdigest() for n, v in generated.items()}
        if actual != expected:
            raise Conflict(
                "Export path already exists with different contents; choose a new output path."
            )
    else:
        root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        stage = Path(tempfile.mkdtemp(prefix=".knowledge-export-", dir=root.parent))
        try:
            for relative, body in generated.items():
                path = stage / relative
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                path.write_bytes(body.encode("utf-8"))
            stage.rename(root)
        except BaseException:
            shutil.rmtree(stage)
            raise
    if output is None:
        # Atomic pointer file, never a mutable database copy or symlink.
        fd, temporary = tempfile.mkstemp(prefix=".LATEST-", dir=root.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(str(root / "index.html") + "\n")
        os.replace(temporary, root.parent / "LATEST.txt")
    return {
        "directory": str(root),
        "snapshot": snapshot,
        "records": len(records),
        "human_view": str(root / "index.html"),
    }
