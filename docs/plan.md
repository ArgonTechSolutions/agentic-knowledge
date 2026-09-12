# Implementation milestones

| Milestone | Status | Acceptance evidence | Rollback |
|---|---|---|---|
| Embedded storage decision | Complete | SQLite/FTS5/sqlite-vec compared with LanceDB and server-based stores; architecture documented | Keep authoritative records; rebuild derived indexes |
| Transactional record tool | Complete | CAS updates, histories/tombstones, atomic conflict-aware bundles, safe backup tested | Preserve store; restore verified backup into a new home |
| Local hybrid retrieval | Complete | Real English/Spanish paraphrases and unrelated-query checks; stale vectors invalidated | Lexical-only mode |
| CLI, exports, skill, installer | Complete | Bounded reads; escaped static HTML; deterministic Markdown; validated skill; Linux and Windows installs verified | Restore backed-up skill/routing; no service cleanup required |
| Private initial rollout | Complete on Linux and Windows | 27 authored notes imported unchanged plus 2 selected decisions; 210 indexed chunks | Original Markdown remains unchanged; preserve new records before switching back |
| Shared distribution | Prepared, not published | Source package and YouTrack/page preview; no private records in source | No public change made |

Validation commands are in README. Publishing a repository/release, YouTrack article or tools.argon.com.pe page is separate from the local implementation and requires confirmation of destination/visibility and exact content. Automatic cross-machine sync and a hosted data service are outside v1; explicit revision bundles are implemented.
