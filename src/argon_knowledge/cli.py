from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from .store import Conflict, KnowledgeError, Store, record_id
from .transfer import export_markdown, markdown_import, read_json, write_new_json


def default_home():
    if os.environ.get("ARGON_KNOWLEDGE_HOME"):
        return Path(os.environ["ARGON_KNOWLEDGE_HOME"]).expanduser()
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "Argon" / "Knowledge"
    return (
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "argon-knowledge"
    )


def parser():
    p = argparse.ArgumentParser(description="Private on-demand knowledge; all commands exit.")
    p.add_argument("--home", type=Path, default=default_home())
    sub = p.add_subparsers(dest="command", required=True)
    for name in ["init", "status", "index"]:
        sub.add_parser(name)
    q = sub.add_parser("search")
    q.add_argument("query")
    q.add_argument("--scope")
    q.add_argument("--mode", choices=["lexical", "semantic", "hybrid"], default="hybrid")
    q.add_argument("--limit", type=int, choices=range(1, 21), default=5)
    q = sub.add_parser("get")
    q.add_argument("id")
    q.add_argument("--revision")
    q.add_argument("--start-line", type=int, default=1)
    q.add_argument("--lines", type=int, default=80)
    q = sub.add_parser("history")
    q.add_argument("id")
    q = sub.add_parser("list")
    q.add_argument("--scope")
    q.add_argument("--include-inactive", action="store_true")
    q = sub.add_parser("put")
    q.add_argument("--file", required=True)
    group = q.add_mutually_exclusive_group(required=True)
    group.add_argument("--id")
    group.add_argument("--key")
    q.add_argument("--expected-revision")
    q = sub.add_parser("set-status")
    q.add_argument("id")
    q.add_argument("status", choices=["active", "superseded", "deleted"])
    q.add_argument("--expected-revision", required=True)
    q = sub.add_parser("import-markdown")
    q.add_argument("root", type=Path)
    q.add_argument("--namespace", required=True)
    q.add_argument("--scope", required=True)
    q.add_argument("--source-revision", default="")
    q.add_argument("--apply", action="store_true")
    q.add_argument("--update", action="store_true")
    q = sub.add_parser("export")
    q.add_argument("--output", type=Path)
    q = sub.add_parser("model-prepare")
    group = q.add_mutually_exclusive_group(required=True)
    group.add_argument("--download", action="store_true")
    group.add_argument("--from-path", type=Path)
    q = sub.add_parser("bundle-export")
    q.add_argument("path", type=Path)
    q = sub.add_parser("bundle-import")
    q.add_argument("path", type=Path)
    q.add_argument("--apply", action="store_true")
    q = sub.add_parser("backup")
    q.add_argument("path", type=Path)
    q = sub.add_parser("sync-enroll")
    q.add_argument("--repository", required=True)
    q.add_argument("--branch", default="main")
    q.add_argument("--device", required=True)
    q.add_argument("--identity", required=True, type=Path)
    q.add_argument("--recipient", required=True, action="append", dest="recipients")
    q.add_argument("--checkout", type=Path)
    q.add_argument("--ssh-key", type=Path)
    sub.add_parser("sync-status")
    q = sub.add_parser("sync-set-recipients")
    q.add_argument("--recipient", required=True, action="append", dest="recipients")
    sub.add_parser("sync")
    return p


def run(args, store):
    command = args.command
    if command in ["init", "status"]:
        return store.status()
    if command == "get":
        if not 1 <= args.lines <= 200 or args.start_line < 1:
            raise KnowledgeError("Use 1-200 lines and a positive start line.")
        item = store.get(args.id, args.revision)
        lines = item.pop("body").splitlines()
        item.update(
            body="\n".join(lines[args.start_line - 1 : args.start_line - 1 + args.lines]),
            start_line=args.start_line,
            total_lines=len(lines),
            next_start_line=(
                args.start_line + args.lines if args.start_line + args.lines <= len(lines) else None
            ),
        )
        return item
    if command == "history":
        return store.history(args.id)
    if command == "list":
        return store.list_records(args.scope, args.include_inactive)
    if command == "put":
        payload = json.load(sys.stdin) if args.file == "-" else read_json(Path(args.file))
        if not isinstance(payload, dict) or "scope" not in payload:
            raise KnowledgeError("Input must be a record object with scope.")
        return store.put(
            args.id or record_id(payload["scope"], args.key), payload, args.expected_revision
        )
    if command == "set-status":
        return store.set_status(args.id, args.status, args.expected_revision)
    if command == "import-markdown":
        return markdown_import(
            store,
            args.root,
            args.namespace,
            args.scope,
            args.source_revision,
            args.apply,
            args.update,
        )
    if command == "export":
        return export_markdown(store, args.output)
    if command == "bundle-export":
        write_new_json(args.path, store.bundle())
        return {"bundle": str(args.path)}
    if command == "bundle-import":
        return store.merge(read_json(args.path), args.apply)
    if command == "backup":
        return store.backup(args.path)
    if command == "sync-enroll":
        from .sync import enroll

        return enroll(
            args.home,
            args.repository,
            args.branch,
            args.device,
            args.identity,
            args.recipients,
            args.checkout,
            args.ssh_key,
        )
    if command == "sync-status":
        from .sync import status

        return status(args.home)
    if command == "sync-set-recipients":
        from .sync import set_recipients

        return set_recipients(args.home, args.recipients)
    if command == "sync":
        from .sync import synchronize

        return synchronize(args.home, store)
    from . import semantic

    if command == "model-prepare":
        return semantic.prepare(args.home, args.from_path, args.download)
    if command == "index":
        return semantic.index(store, args.home)
    if command == "search":
        return semantic.search(store, args.home, args.query, args.scope, args.mode, args.limit)
    raise KnowledgeError("Unknown command.")


def main():
    args = parser().parse_args()
    store = None
    try:
        args.home = args.home.expanduser().absolute()
        store = Store(args.home / "knowledge.sqlite3", create=args.command == "init")
        result = run(args, store)
        if args.command in ["put", "set-status", "sync"] or (
            args.command in ["import-markdown", "bundle-import"] and args.apply
        ):
            try:
                result["export"] = export_markdown(store)
            except (OSError, KnowledgeError) as exc:
                result["warning"] = f"Records committed but export failed: {exc}; run export."
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeError, OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}), file=sys.stderr)
        return 3 if isinstance(exc, Conflict) else 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
