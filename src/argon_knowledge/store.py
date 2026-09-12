from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
KINDS = {"fact", "preference", "decision", "procedure", "reference", "outcome"}
STATES = {"active", "superseded", "deleted"}
VERIFICATION = {"verified", "reported", "unverified"}
FIELDS = {
    "scope",
    "kind",
    "title",
    "body",
    "source",
    "source_revision",
    "tags",
    "verification",
    "status",
}
SQL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE revisions (
 revision TEXT PRIMARY KEY, record_id TEXT NOT NULL, parent TEXT,
 payload TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX revision_record ON revisions(record_id);
CREATE TABLE records (
 id TEXT PRIMARY KEY, head TEXT NOT NULL REFERENCES revisions(revision),
 scope TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 source TEXT NOT NULL, status TEXT NOT NULL, verification TEXT NOT NULL
);
CREATE INDEX record_scope ON records(scope,status);
CREATE TABLE chunks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT NOT NULL REFERENCES records(id),
 revision TEXT NOT NULL, heading TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 start_line INTEGER NOT NULL, end_line INTEGER NOT NULL
);
CREATE INDEX chunk_record ON chunks(record_id);
CREATE VIRTUAL TABLE chunks_fts USING fts5(title,heading,body,content='chunks',content_rowid='id',
 tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER chunk_insert AFTER INSERT ON chunks BEGIN
 INSERT INTO chunks_fts(rowid,title,heading,body) VALUES(new.id,new.title,new.heading,new.body);
END;
CREATE TRIGGER chunk_delete AFTER DELETE ON chunks BEGIN
 INSERT INTO chunks_fts(chunks_fts,rowid,title,heading,body)
 VALUES('delete',old.id,old.title,old.heading,old.body);
END;
CREATE TABLE embeddings (
 chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
 model TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY(chunk_id,model)
);
"""


class KnowledgeError(Exception):
    pass


class Conflict(KnowledgeError):
    pass


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def record_id(scope, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"argon-knowledge:{scope}:{key}"))


def check_id(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise KnowledgeError("Record ID must be a canonical UUID.") from None


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise KnowledgeError("Record fields do not match the versioned contract.")
    for key in ["scope", "kind", "title", "body", "source", "verification", "status"]:
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise KnowledgeError(f"{key} must be a nonempty string.")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,119}", payload["scope"]):
        raise KnowledgeError("Invalid scope.")
    if payload["kind"] not in KINDS or payload["status"] not in STATES:
        raise KnowledgeError("Invalid kind or status.")
    if payload["verification"] not in VERIFICATION:
        raise KnowledgeError("Invalid verification state.")
    if not isinstance(payload["source_revision"], str) or len(payload["source_revision"]) > 256:
        raise KnowledgeError("Invalid source revision.")
    if (
        len(payload["body"]) > 500_000
        or len(payload["title"]) > 300
        or len(payload["source"]) > 2000
    ):
        raise KnowledgeError("Record exceeds a size limit.")
    tags = payload["tags"]
    if (
        not isinstance(tags, list)
        or len(tags) > 30
        or any(not isinstance(x, str) or not x or len(x) > 80 for x in tags)
    ):
        raise KnowledgeError("Invalid tags.")
    # Defense in depth, not a general secret classifier. Never echo rejected content.
    text = canonical(payload)
    if re.search(
        r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}|\bgh[pousr]_[A-Za-z0-9]{30,}|\bBearer [A-Za-z0-9._-]{30,}",
        text,
    ):
        raise KnowledgeError("Possible credential material rejected; review the input locally.")


def chunks(body, maximum=800):
    """Bounded line-preserving chunks, with section context. Long lines retain their line number."""
    heading = ""
    buf = []
    size = 0
    start = 1
    end = 1
    fence = False
    for number, line in enumerate(body.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        is_heading = not fence and re.match(r"^#{1,6}\s+", line)
        if is_heading or size + len(line) + 1 > maximum:
            if buf:
                yield heading, "\n".join(buf), start, end
                buf, size = [], 0
            if is_heading:
                heading = line.lstrip("# ").strip()
        for offset in range(0, max(len(line), 1), maximum):
            part = line[offset : offset + maximum]
            if not buf:
                start = number
            buf.append(part)
            size += len(part) + 1
            end = number
            if size >= maximum:
                yield heading, "\n".join(buf), start, end
                buf, size = [], 0
    if buf:
        yield heading, "\n".join(buf), start, end


class Store:
    def __init__(self, path, create=False):
        self.path = Path(path).expanduser().absolute()
        if self.path.is_symlink():
            raise KnowledgeError("Database must not be a symlink.")
        exists = self.path.exists()
        if not exists and not create:
            raise KnowledgeError("Knowledge store is missing. Run init with the intended --home.")
        if not exists:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Reserve a private file without replacing an existing target.
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if not exists:
            self.db.executescript("BEGIN IMMEDIATE;\n" + SQL + f"\nPRAGMA user_version={SCHEMA};")
            self.db.execute("INSERT INTO metadata VALUES(?,?)", ("store_id", str(uuid.uuid4())))
            self.db.commit()
        elif version != SCHEMA:
            self.close()
            raise KnowledgeError(f"Unsupported database schema {version}; expected {SCHEMA}.")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        if self.db.in_transaction:
            yield
            return
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def get(self, identifier, revision=None):
        check_id(identifier)
        if revision:
            row = self.db.execute(
                "SELECT * FROM revisions WHERE record_id=? AND revision=?", (identifier, revision)
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT v.* FROM records r JOIN revisions v ON r.head=v.revision WHERE r.id=?",
                (identifier,),
            ).fetchone()
        if not row:
            raise KnowledgeError("Record or revision not found.")
        return {
            "id": identifier,
            "revision": row["revision"],
            "parent": row["parent"],
            "recorded_at": row["created_at"],
            **json.loads(row["payload"]),
        }

    def history(self, identifier):
        current = self.get(identifier)
        result = []
        while current:
            result.append(
                {k: current[k] for k in ["id", "revision", "parent", "recorded_at", "status"]}
            )
            current = self.get(identifier, current["parent"]) if current["parent"] else None
        return result

    def _head(self, identifier, revision, payload):
        self.db.execute(
            """INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET head=excluded.head,scope=excluded.scope,kind=excluded.kind,
          title=excluded.title,body=excluded.body,source=excluded.source,status=excluded.status,
          verification=excluded.verification""",
            (
                identifier,
                revision,
                *[
                    payload[k]
                    for k in ["scope", "kind", "title", "body", "source", "status", "verification"]
                ],
            ),
        )
        self.db.execute("DELETE FROM chunks WHERE record_id=?", (identifier,))
        if payload["status"] == "active":
            for heading, body, start, end in chunks(payload["body"]):
                self.db.execute(
                    "INSERT INTO chunks(record_id,revision,heading,title,body,start_line,end_line) VALUES(?,?,?,?,?,?,?)",
                    (identifier, revision, heading, payload["title"], body, start, end),
                )

    def put(self, identifier, payload, expected=None):
        check_id(identifier)
        validate_payload(payload)
        with self.transaction():
            existing = self.db.execute(
                "SELECT head FROM records WHERE id=?", (identifier,)
            ).fetchone()
            parent = existing["head"] if existing else None
            if parent:
                old = self.db.execute(
                    "SELECT payload FROM revisions WHERE revision=?", (parent,)
                ).fetchone()[0]
                if canonical(payload) == old:
                    return {"id": identifier, "revision": parent, "changed": False}
            if parent != expected:
                raise Conflict("Revision conflict; retrieve the current record before updating.")
            created = now()
            version = {
                "record_id": identifier,
                "parent": parent,
                "payload": payload,
                "created_at": created,
            }
            rev = digest(version)
            self.db.execute(
                "INSERT INTO revisions VALUES(?,?,?,?,?)",
                (rev, identifier, parent, canonical(payload), created),
            )
            self._head(identifier, rev, payload)
            return {"id": identifier, "revision": rev, "changed": True}

    def set_status(self, identifier, status, expected):
        current = self.get(identifier)
        payload = {k: current[k] for k in FIELDS}
        payload["status"] = status
        return self.put(identifier, payload, expected)

    def list_records(self, scope=None, include_inactive=False):
        where = ["1=1"]
        values = []
        if scope:
            where.append("scope=?")
            values.append(scope)
        if not include_inactive:
            where.append("status='active'")
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,head AS revision,scope,kind,title,source,status,verification FROM records WHERE "
                + " AND ".join(where)
                + " ORDER BY scope,title,id",
                values,
            )
        ]

    def status(self):
        return {
            "schema": SCHEMA,
            "store_id": self.db.execute(
                "SELECT value FROM metadata WHERE key=?", ("store_id",)
            ).fetchone()[0],
            "records": self.db.execute("SELECT count(*) FROM records").fetchone()[0],
            "active_records": self.db.execute(
                "SELECT count(*) FROM records WHERE status='active'"
            ).fetchone()[0],
            "chunks": self.db.execute("SELECT count(*) FROM chunks").fetchone()[0],
            "revisions": self.db.execute("SELECT count(*) FROM revisions").fetchone()[0],
            "embedding_models": [
                dict(x)
                for x in self.db.execute(
                    "SELECT model,count(*) AS indexed_chunks FROM embeddings GROUP BY model"
                )
            ],
            "database_bytes": self.path.stat().st_size,
        }

    def lexical(self, query, scope=None, limit=60):
        words = re.findall(r"[^\W_]+", query, re.UNICODE)[:24]
        if not words:
            return []
        expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
        sql = """SELECT c.*,r.scope,r.kind,r.source,r.verification,
          bm25(chunks_fts,4.0,2.0,1.0) AS rank FROM chunks_fts
          JOIN chunks c ON c.id=chunks_fts.rowid JOIN records r ON r.id=c.record_id
          WHERE chunks_fts MATCH ? AND r.status='active' """
        args = [expression]
        if scope:
            sql += " AND r.scope=?"
            args.append(scope)
        sql += " ORDER BY rank,c.id LIMIT ?"
        args.append(limit)
        return [dict(x) for x in self.db.execute(sql, args)]

    def vector(self, vector, model, scope=None, limit=60, minimum=0.28):
        import sqlite_vec

        self.db.enable_load_extension(True)
        try:
            sqlite_vec.load(self.db)
        finally:
            self.db.enable_load_extension(False)
        sql = """SELECT c.*,r.scope,r.kind,r.source,r.verification,
          1-vec_distance_cosine(e.vector,?) AS similarity
          FROM embeddings e JOIN chunks c ON e.chunk_id=c.id JOIN records r ON r.id=c.record_id
          WHERE e.model=? AND r.status='active' """
        args = [sqlite_vec.serialize_float32(vector), model]
        if scope:
            sql += " AND r.scope=?"
            args.append(scope)
        sql += " AND (1-vec_distance_cosine(e.vector,?)) >= ? ORDER BY similarity DESC,c.id LIMIT ?"
        args += [sqlite_vec.serialize_float32(vector), minimum, limit]
        return [dict(x) for x in self.db.execute(sql, args)]

    def bundle(self):
        with self.transaction():
            revisions = []
            for row in self.db.execute("SELECT * FROM revisions ORDER BY created_at,revision"):
                value = dict(row)
                value["payload"] = json.loads(value["payload"])
                revisions.append(value)
            return {
                "format": "argon-knowledge-bundle/v1",
                "heads": {
                    x["id"]: x["head"]
                    for x in self.db.execute("SELECT id,head FROM records ORDER BY id")
                },
                "revisions": revisions,
            }

    def merge(self, bundle, apply=False):
        if (
            not isinstance(bundle, dict)
            or set(bundle) != {"format", "heads", "revisions"}
            or bundle["format"] != "argon-knowledge-bundle/v1"
        ):
            raise KnowledgeError("Invalid record bundle format.")
        if not isinstance(bundle["heads"], dict) or not isinstance(bundle["revisions"], list):
            raise KnowledgeError("Invalid bundle collections.")
        versions = {}
        for item in bundle["revisions"]:
            if not isinstance(item, dict) or set(item) != {
                "revision",
                "record_id",
                "parent",
                "payload",
                "created_at",
            }:
                raise KnowledgeError("Invalid bundle revision.")
            check_id(item["record_id"])
            validate_payload(item["payload"])
            if not isinstance(item["created_at"], str) or len(item["created_at"]) > 60:
                raise KnowledgeError("Invalid revision date.")
            if item["parent"] is not None and not re.fullmatch("[0-9a-f]{64}", str(item["parent"])):
                raise KnowledgeError("Invalid parent revision.")
            if digest({k: v for k, v in item.items() if k != "revision"}) != item["revision"]:
                raise KnowledgeError("Bundle revision integrity check failed.")
            if item["revision"] in versions:
                raise KnowledgeError("Duplicate revision in bundle.")
            versions[item["revision"]] = item
        chains = {}
        reachable = set()
        for identifier, head in bundle["heads"].items():
            check_id(identifier)
            chain = []
            cursor = head
            while cursor is not None:
                if (
                    cursor in chain
                    or cursor not in versions
                    or versions[cursor]["record_id"] != identifier
                ):
                    raise KnowledgeError("Broken, cyclic, or cross-record revision chain.")
                chain.append(cursor)
                cursor = versions[cursor]["parent"]
            if not chain:
                raise KnowledgeError("Empty record history.")
            chains[identifier] = chain
            reachable.update(chain)
        if reachable != set(versions):
            raise KnowledgeError("Bundle contains unreachable revisions.")
        with self.transaction():
            updates = []
            conflicts = []
            for identifier, chain in chains.items():
                old = self.db.execute(
                    "SELECT head FROM records WHERE id=?", (identifier,)
                ).fetchone()
                local = old["head"] if old else None
                incoming = chain[0]
                if local == incoming:
                    continue
                if local is None or local in chain:
                    updates.append(identifier)
                elif self.db.execute(
                    "SELECT 1 FROM revisions WHERE record_id=? AND revision=?",
                    (identifier, incoming),
                ).fetchone():
                    continue  # Local already descends from the incoming snapshot.
                else:
                    conflicts.append(identifier)
            if conflicts:
                raise Conflict(
                    "Divergent record heads: " + ", ".join(conflicts[:20]) + "; no records applied."
                )
            if apply:
                for identifier in updates:
                    for rev in reversed(chains[identifier]):
                        v = versions[rev]
                        self.db.execute(
                            "INSERT OR IGNORE INTO revisions VALUES(?,?,?,?,?)",
                            (
                                rev,
                                identifier,
                                v["parent"],
                                canonical(v["payload"]),
                                v["created_at"],
                            ),
                        )
                    head = chains[identifier][0]
                    self._head(identifier, head, versions[head]["payload"])
            return {"apply": apply, "records_to_update": len(updates), "record_ids": updates}

    def backup(self, destination):
        target = Path(destination).expanduser().absolute()
        if target.exists():
            raise KnowledgeError("Backup destination already exists.")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with sqlite3.connect(target) as dest:
            self.db.backup(dest)
            if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise KnowledgeError("Backup integrity check failed.")
        return {"backup": str(target), "bytes": target.stat().st_size}
