# Record writes

Write a temporary UTF-8 JSON file (or pass JSON via stdin with `--file -`):

```json
{
  "scope": "personal",
  "kind": "preference",
  "title": "On-demand knowledge tools",
  "body": "The owner prefers tools that exit after use and leave no background model or service running.",
  "source": "conversation:<actual-task-id>",
  "source_revision": "",
  "tags": ["tooling"],
  "verification": "reported",
  "status": "active"
}
```

Replace the example with actual evidence. All fields are required. Kinds: fact, preference, decision, procedure, reference, outcome. Verification: reported (owner stated), verified (checked evidence), unverified (reference or uncertainty). Status: active, superseded, deleted. Source is a real task, document, URL or other recoverable origin; do not fabricate an ID. Use source_revision for a Git hash or document revision when available.

When a record contains an absolute filesystem path, its body must place the verified device beside it:

```text
Device: windows-workstation
Path: D:\Work\Example
```

Add a matching `device:windows-workstation` tag. Determine the stable device label from the environment or established device inventory. Do not infer it from the path, omit it, or silently generalize a path across devices. If one logical resource has different paths on multiple devices, keep each device/path mapping explicit in the same record or in clearly linked records.

Commands, after `python <skill>/scripts/run.py`:

- New: `put --key stable-descriptive-key --file /path/record.json`. The key plus scope produces a stable ID; retries with identical content are idempotent.
- Existing: `put --id UUID --expected-revision HASH --file /path/record.json`.
- History: `history UUID`; `get UUID --revision HASH --lines 60`.
- Retire: `set-status UUID superseded --expected-revision HASH`.
- Refresh changed embeddings: `index`.

Deletion is a tombstone; revision history and previous exports retain the content. This is not secure erasure. Never put secrets in the tool. Its credential-pattern check is only defense in depth.
