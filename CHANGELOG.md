# Releases

## 0.2.0

Adds opt-in one-shot synchronization through any enrolled Git repository. Full revision bundles are encrypted locally with `age`, grouped by recipient set, and stored as immutable device-labelled snapshots. Sync merges compatible histories transactionally, retries ordinary concurrent Git pushes, and stops on divergent record heads. The skill now always routes relevant personal context, separates personal and YouTrack knowledge, removes personal setup details from shared writing, and requires device provenance for absolute paths.

## 0.1.0

Initial public release: on-demand SQLite records and revisions, FTS5/sqlite-vec hybrid retrieval, local multilingual embeddings, Markdown/HTML exports, private backups, conflict-detecting transfer bundles, and an opt-in Codex capture skill. Linux and Windows installation supported. No daemon, hosted data service or background synchronization.

SQLite schema version 1. Automatic capture defaults off. Source archives include the installer and skill; Python wheels provide the CLI. The model is downloaded separately. Real semantic retrieval was tested on Linux and Windows; lightweight CI tests do not download model weights.
