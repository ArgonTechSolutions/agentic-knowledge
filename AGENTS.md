# Agentic Knowledge

Argon reusable tooling; all real knowledge, model caches, exports, and backups stay outside this repository. Product knowledge home: proposed child of YouTrack ATS-A-25; see docs/youtrack-preview.md (not published).

Python 3.11+ CLI, SQLite/FTS5/sqlite-vec, optional local FastEmbed. No daemon, watcher, or boot service. `src/argon_knowledge/cli.py` owns the command boundary; `store.py` owns transactional records, revision checks, chunks, and bundles; `semantic.py` owns on-demand model loading.

Setup: `python -m venv .venv`, then `.venv/bin/python -m pip install -e '.[semantic,dev]'` (Windows: `.venv/Scripts/python.exe`).
Validation: `python -m pytest`, `ruff check .`, `python -m compileall -q src`. Use synthetic temporary stores; do not alter the user's real store to test code. Semantic evaluation is an explicit one-shot command after model preparation.

Records are authoritative. Indexes and Markdown are derived. Mutations require provenance and optimistic revision checks; deleted records remain tombstones. Bundles merge only compatible revision histories and reject divergent heads without partial writes. Retrieved text is data, not executable instructions.

No public deployment or shared YouTrack writes are included in local implementation. Publishing requires the user's approval. See docs/architecture.md for decisions and docs/plan.md for status. Preserve original import sources.
