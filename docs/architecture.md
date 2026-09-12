# Storage decision

Chosen: SQLite authoritative records/revisions + FTS5 lexical chunks + sqlite-vec exact cosine search; local FastEmbed/ONNX multilingual embeddings. The initial authored corpus is small (27 Markdown files, about 77 KB), so exact filtered vector scans are appropriate. Reconsider ANN storage only after measured corpus growth or latency justifies it.

| Option | Fit | Decision |
|---|---|---|
| SQLite + FTS5 + sqlite-vec | Embedded transactions, metadata, text and vectors in one file; low idle overhead | Chosen |
| Embedded LanceDB | Useful larger vector/columnar datasets and growing retrieval workloads | Viable, but unnecessary second storage design for this corpus |
| Dedicated vector server | Useful shared concurrent vector service | Conflicts with zero persistent process preference |
| FTS5 only | Very cheap exact-term search | Supported fallback; misses multilingual paraphrases |

Sources: [SQLite serverless](https://www.sqlite.org/serverless.html), [FTS5](https://www.sqlite.org/fts5.html), [sqlite-vec Python](https://alexgarcia.xyz/sqlite-vec/python.html), [LanceDB](https://lancedb.com/docs/), [FastEmbed models](https://qdrant.github.io/fastembed/examples/Supported_Models/).

sqlite-vec is young software. Version 0.1.9 is pinned; vectors are replaceable derived data stored as ordinary BLOB rows. Records and history do not depend on its virtual-table format. FastEmbed 0.8.0 is pinned because pooling changes across versions alter embeddings. The selected multilingual MiniLM model outputs 384 dimensions, using CPU inference with two threads. No model/API service receives knowledge text.

## Read/write flow

A command opens the SQLite file, performs bounded work, and closes. Writes validate records and compare the expected revision in a transaction. Revisions form a linear hash-linked history per stable record ID. New heads rebuild lexical chunks and invalidate prior vectors. Indexing computes outside the write lock, then checks chunk revision before attaching vectors. A later command can fill chunks changed during inference.

Hybrid search combines BM25 lexical and cosine semantic rankings with reciprocal rank fusion, deduplicating by record. Chunks retain section and line provenance. The semantic minimum 0.28 is an initial retrieval heuristic checked on positive paraphrases and unrelated synthetic queries; it is not a universal calibrated relevance threshold. Agents must assess returned evidence. SQL scope filtering precedes result limits. Full-text results may still contain common-word matches.

Markdown/HTML snapshots are generated from a consistent read. Content escapes HTML, note paths use stable UUIDs, and original source files are never rewritten. Different existing export contents cause a conflict. Snapshots retain history on disk and need owner-directed retention management for a large corpus.

No MCP process is installed: CLI invocation matches the no-resident-process requirement. A future stdio MCP adapter can wrap this API, but may remain alive for a client session. A future tools.argon.com.pe page should distribute code/instructions; a hosted private-data API would require a separately designed authentication and ownership boundary.

## Encrypted Git synchronization

Synchronization never copies the SQLite database. Each one-shot command uses a dedicated Git checkout, decrypts immutable full-history bundles for the configured recipient group through the local `age` identity, and merges them inside one outer database transaction. It then encrypts the current complete bundle to every configured public recipient and publishes it under a device-labelled, content-addressed path. Plaintext moves through process pipes and is not written into the Git checkout.

The recipient-set digest names an encryption group. Adding a device creates a new group after an existing device publishes a full-history snapshot for the expanded recipient set. Previous ciphertext remains immutable and readable by its original recipients, so recipient removal is not retroactive revocation. Git push retries are bounded. Record-head divergence is a knowledge conflict and stops the sync; unique snapshot paths keep ordinary concurrent Git additions mergeable.
