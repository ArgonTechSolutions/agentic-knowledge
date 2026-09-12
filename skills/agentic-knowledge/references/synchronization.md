# Cross-device synchronization

Each device has an independent authoritative SQLite store. Enrolled synchronization uses a dedicated checkout of any Git remote and stores only immutable `age`-encrypted full-history bundles. Git credentials and age private keys remain outside the repository. The `sync` command pulls, merges compatible histories transactionally, publishes the current device snapshot, and exits.

Run `sync-status` to distinguish an enrolled device from a local-only installation. On an enrolled device, run `sync` before relying on personal knowledge and after a successful capture batch. A successful result names the device, recipient group, bundle hash, imported-record count, and published snapshot. Treat an error as a freshness boundary.

Each absolute path in a personal record must still name its verified device. Synchronization makes that record available elsewhere; it does not make the path portable.

## Enroll a repository

Use a private repository and existing Git authentication. Never embed a token in the repository URL. Enrollment requires Git, `age`, a local age identity, all intended devices' public age recipients, a stable device label, and an empty or existing remote branch. It creates a dedicated checkout under the private data home by default. Follow the installation guide's exact command.

To add a device with a distinct age identity, first run `sync-set-recipients` on an already enrolled device with the complete old-plus-new recipient set, then run `sync` there. This publishes a full-history snapshot in a new recipient group. Update every other existing device to the same complete set before further writes. Enroll and sync the new device using that set. Old encrypted groups remain in Git history, so removing a recipient affects future groups and is not retroactive revocation.

## Conflict and fallback

The importer applies no bundle batch when it detects divergent heads. Preserve both device stores and encrypted repository history, inspect the affected record histories, and reconcile intentionally on one device. Do not force an overwrite or discard either copy.

For a manual fallback, use `bundle-export` on the source, transfer the plaintext bundle only through an authenticated encrypted channel, preview `bundle-import` on the destination, repeat with `--apply`, then run `index`.

Never synchronize `knowledge.sqlite3` while it is open. Do not synchronize generated Markdown/HTML exports as if they were authoritative. Bundles include records and complete revision history but exclude embeddings and model files.
