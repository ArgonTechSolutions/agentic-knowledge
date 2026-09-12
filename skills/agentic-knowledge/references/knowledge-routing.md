# Personal and shared knowledge routing

Choose the store from who should use the fact and whether it describes one owner's environment.

| Knowledge | Authority | Treatment |
|---|---|---|
| Personal preferences, private decisions, cross-project lessons | Personal Agentic Knowledge | May be specific to the owner; capture under the selected-memory policy. |
| Absolute paths, usernames, device names, SSH aliases, local checkout state | Personal Agentic Knowledge | Record the verified device with every path. |
| Argon process, architecture, project contracts, deployment procedures, shared pitfalls | YouTrack MCP | Write portable content for authorized team readers. |
| A local observation that reveals a shared defect | Both when useful | Keep local evidence personal; put only the verified, portable conclusion and reproduction details in YouTrack. |

Before creating or updating YouTrack content, remove personal environment details. Omit home directories, absolute checkout paths, usernames, private host aliases, editor or Codex state, and device-specific commands. Replace them with repository-relative paths, canonical repository names or URLs, role-based host names, and portable commands when those details are useful.

For example, do not write:

```text
Workspace: /home/gonzalo/Work/GBGlobalV2, containing separate backend and frontend Git repositories.
```

If the repository structure matters to the shared work, write:

```text
The project uses separate backend and frontend Git repositories.
```

If it does not affect the ticket or article, omit it. Never copy a personal record wholesale into YouTrack. Query personal knowledge to inform the work, then author shared content from verified project facts. Preserve the user's existing authorization requirements for YouTrack writes; routing a fact to YouTrack does not authorize a mutation.
