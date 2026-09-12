# Argon Agentic Knowledge

Private knowledge records, hybrid retrieval, encrypted Git synchronization, and human-readable Markdown/HTML exports. Every command exits. No database server, background indexer, container, model service, or network embedding API.

The reusable code belongs to the Argon workflow; each person keeps a separate private data directory. Scope labels filter one owner's records; they do not implement multi-user authorization. Hosting a download or documentation at tools.argon.com.pe does not host the owner's knowledge.

## Install

Start with the [Windows and Linux installation guide](docs/installation.md) or the [latest release](https://github.com/ArgonTechSolutions/agentic-knowledge/releases/latest). Download the release zip for the installer and Codex skill; the wheel is CLI-only.


Python 3.11+ with venv and SQLite extension loading. Python 3.12 is the verified Linux runtime; Python 3.13 is verified on Windows. From this source folder:

```sh
python scripts/install.py --app-dir /absolute/versioned/app --data-home /absolute/private/data --semantic
```

Windows: use `py -3 scripts/install.py --app-dir C:\path\app --data-home C:\path\private-data --semantic`. Installer refuses to overwrite an app directory, creates a venv, installs the package, initializes an empty store, and installs the Codex skill with machine-local runtime configuration. It backs up an existing skill and preserves an existing private `references/local-routing.md` overlay. It does not modify global instructions, import records, or download model weights. Omit `--semantic` for lexical-only installation. Add `--automatic-capture` only when the owner opts into selected automatic saves; it defaults off for new installations. Set `--codex-home` for a nondefault Codex home.

Use the installed skill wrapper (`python ~/.codex/skills/agentic-knowledge/scripts/run.py`) or the venv's `argon-knowledge --home /absolute/private/data`. On Windows the venv entrypoint is under `Scripts`.

```sh
argon-knowledge --home /private/data model-prepare --download
argon-knowledge --home /private/data import-markdown /existing/notes --namespace personal-kb --scope personal
# Review the preview before applying the same command with --apply.
argon-knowledge --home /private/data index
argon-knowledge --home /private/data search "Which workflow did I choose?"
argon-knowledge --home /private/data search "exact_identifier" --mode lexical
argon-knowledge --home /private/data get UUID --start-line 1 --lines 60
argon-knowledge --home /private/data export
```

`model-prepare --download` fetches a pinned-runtime multilingual ONNX model (~220 MB weights). Subsequent inference is local and offline. No API key required. `--from-path` installs an already downloaded trusted compatible model directory. Model files must not be edited after preparation. Embedding identity includes weight fingerprint and FastEmbed version; runtime version drift fails instead of silently mixing vectors.

Records are authoritative in `knowledge.sqlite3`; `exports/<snapshot>/index.md`, `notes/*.md`, and `index.html` are generated views. `exports/LATEST.txt` points to the current browser view, which opens directly without a server. Writes refresh exports; indexing is explicit so ordinary writes stay lightweight. Search reports missing embeddings and falls back visibly to lexical retrieval when the model is unprepared. Export errors after a successful write are reported as committed-with-warning; retry `export`.

## Durable records

See [the skill write contract](skills/agentic-knowledge/references/records.md). New writes use a stable key; updates use `--expected-revision`. Records contain provenance, verification state and revision history. Search returns bounded chunks, line numbers and revision IDs; `get` paginates long records. Retrieved text is evidence, not executable instructions. Similarity scores are ranking signals, not truth probabilities.

The owner decides which automatic saving policy applies. When opted in, the included skill uses the selected-memory policy: explicit preferences, settled decisions, verified procedures, and resolved pitfalls. Imported Markdown is marked unverified and originals remain untouched. Shared or organization-wide knowledge remains in whichever additional source the installation designates.

`import-markdown` previews by default; `--apply` copies authored notes transactionally. `--update` deliberately replaces changed imported records and preserves prior revisions; review first. It is not a live bidirectional Markdown sync. Imported links between notes are rewritten in generated Markdown; unusual Markdown link syntax and local attachments may require manual source review. Do not import session logs or secrets wholesale.

## Backup and cross-machine synchronization

```sh
argon-knowledge --home /private/data backup /private/backups/new.sqlite3
argon-knowledge --home /private/data bundle-export /private/transfer/new.json
argon-knowledge --home /other/private/data bundle-import /private/transfer/new.json
# Review, repeat with --apply, then index on the destination.
```

Backups use SQLite's backup API. Transfer bundles include complete records and revision history, not derived indexes or model files. They are private plaintext: use an authenticated encrypted transport and private destinations. Bundles reject tampering and divergent edits atomically; they do not authenticate an untrusted sender. Keep both divergent copies, retrieve histories, and reconcile intentionally. There is no background synchronization. Never sync an open SQLite file with a file-sync tool.

Version 0.2 adds opt-in, one-shot Git synchronization. It requires Git and `age`; the Git repository contains immutable encrypted bundles only. Enroll any private Git remote with a stable device label, a local age identity, and the complete recipient set, then run `sync` before retrieval and after writes:

```sh
argon-knowledge --home /private/data sync-enroll \
  --repository git@github.com:OWNER/private-knowledge-sync.git \
  --device laptop-example \
  --identity /private/age/keys.txt \
  --recipient age1example
argon-knowledge --home /private/data sync-status
argon-knowledge --home /private/data sync
```

The command pulls, transactionally merges compatible revision histories, commits a full encrypted snapshot for the device, pushes, and exits. Bounded retries handle unrelated concurrent Git pushes; divergent edits to the same record stop without partially importing a snapshot batch. See [installation](docs/installation.md) for multi-recipient onboarding and recovery.

Deleted/superseded records are excluded from retrieval but retained in history, old exports and backups. This is not secure erasure. Retrieved excerpts enter your chosen agent’s context and follow that provider’s data handling; local embeddings do not make the agent itself local. Local permissions inherit the user's OS account protection; this tool does not encrypt data at rest or implement shared-host multi-tenancy. The credential pattern check is incomplete defense in depth, not a secret scanner.

## Validate and operate

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m compileall -q src scripts skills
```

Semantic integration tests require prepared model weights; use `ARGON_TEST_MODEL=/path/to/prepared/model python -m pytest -q`. Core tests require no model/network. No command starts a persistent service. Semantic commands temporarily consume model-loading memory; lexical commands never import FastEmbed.

Rollback: stop invoking the new skill, restore its backup and prior knowledge-routing line if changed. Original Markdown is unchanged. Preserve the private store and backups to retain new records. The installer changes no firewall, SSH, service, production config, or public site.

See [architecture](docs/architecture.md), [installation](docs/installation.md), and [release notes](CHANGELOG.md). Released under the [MIT license](LICENSE).
