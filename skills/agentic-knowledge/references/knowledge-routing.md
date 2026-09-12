# Knowledge-source routing

Choose the store from who should use the fact and whether it describes one owner's environment.

| Knowledge | Authority | Treatment |
|---|---|---|
| Personal preferences, private decisions, cross-project lessons | Personal Agentic Knowledge | May be specific to the owner; capture under the selected-memory policy. |
| Absolute paths, usernames, device names, SSH aliases, local checkout state | Personal Agentic Knowledge | Record the verified device with every path. |
| Shared process, architecture, project contracts, deployment procedures, shared pitfalls | Configured shared knowledge source | Write portable content for its authorized readers. |
| A local observation that reveals a shared defect | Both when useful | Keep local evidence personal; put only the verified, portable conclusion and reproduction details in the relevant shared source. |

Before creating or updating shared content, remove personal environment details. Omit home directories, absolute checkout paths, usernames, private host aliases, editor or agent state, and device-specific commands. Replace them with repository-relative paths, canonical repository names or URLs, role-based host names, and portable commands when those details are useful.

For example, do not write:

```text
Workspace: /home/example/work/project, containing separate API and web Git repositories.
```

If the repository structure matters to the shared work, write:

```text
The project uses separate API and web Git repositories.
```

If it does not affect the shared artifact, omit it. Never copy a personal record wholesale into another source. Query personal knowledge to inform the work, then author shared content from verified project facts. Preserve the user's existing authorization requirements for writes; routing a fact to a source does not authorize a mutation.
