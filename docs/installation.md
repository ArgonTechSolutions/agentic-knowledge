# Install Agentic Knowledge

Use a separate private store for each person. This is local CLI software with a Codex skill; no daemon or hosted account is required. Python 3.12 or 3.13 with pip and venv is recommended (both tested). Linux Python needs SQLite extension loading. Install your operating system's Python/venv packages first if missing.

## 1. Download

Download **agentic-knowledge-v0.1.0.zip** from the [v0.1.0 release](https://github.com/ArgonTechSolutions/agentic-knowledge/releases/tag/v0.1.0), verify its SHA-256 against `SHA256SUMS.txt`, extract it, and open a terminal in the extracted directory. The zip includes the installer and Codex skill. Alternatively:

```sh
git clone https://github.com/ArgonTechSolutions/agentic-knowledge.git
cd agentic-knowledge
git checkout v0.1.0
```

## 2. Install on Linux

Run from the downloaded source folder. The destination must not exist and must be outside the source directory.

```sh
python3 scripts/install.py \
  --app-dir "$HOME/.local/opt/agentic-knowledge-0.1.0" \
  --data-home "$HOME/.local/share/argon-knowledge" \
  --semantic
python3 "$HOME/.codex/skills/agentic-knowledge/scripts/run.py" status
```

## 2. Install on Windows

Run in PowerShell from the downloaded source folder:

```powershell
py -3 scripts/install.py `
  --app-dir "$env:LOCALAPPDATA\Argon\Apps\agentic-knowledge-0.1.0" `
  --data-home "$env:LOCALAPPDATA\Argon\Knowledge" `
  --semantic
py -3 "$HOME\.codex\skills\agentic-knowledge\scripts\run.py" status
```

The installer creates a private application venv, initializes the store, and installs the skill. It honors `CODEX_HOME`, or accepts `--codex-home PATH`. Adjust wrapper paths accordingly. A pre-existing skill is backed up under the Codex home's `backups/` directory. No global instructions, services or existing notes are changed.

**Automatic saving is opt-in.** Add `--automatic-capture` to the installer only if you want agents to save selected durable preferences, decisions and verified procedures without asking each time. Otherwise they save only when explicitly requested. `run.py policy` reports the current setting. For an existing installation, deliberately edit `automatic_capture` in the installed skill's `runtime.json` to enable or disable it; preserve the interpreter and data paths.

## 3. Prepare search

Use `python3` on Linux or `py -3` on Windows for the wrapper commands below:

```sh
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py model-prepare --download
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py index
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py search "What decisions have I saved?"
```

On Windows, use the quoted wrapper path shown above. The explicit preparation command downloads roughly 220 MB of multilingual model weights. Queries embed text locally; no embedding API key is required. Semantic inference temporarily consumes RAM and releases it on command exit. For a lightweight lexical-only setup, omit `--semantic`, skip model preparation, and use `search "exact terms" --mode lexical`.

An empty initial store correctly returns no records. Start a new Codex task and ask it to use `$agentic-knowledge`. For automatic routing, add this narrow line to your own Codex instructions if desired:

> Use the agentic-knowledge skill for relevant personal context and durable captures, respecting the installation's capture policy.

## 4. Import existing notes and open the human view

Replace the directory with your authored Markdown folder. Preview first, then repeat with `--apply` after reviewing the result:

```sh
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py import-markdown /absolute/notes --namespace personal-notes --scope personal
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py import-markdown /absolute/notes --namespace personal-notes --scope personal --apply
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py index
python3 ~/.codex/skills/agentic-knowledge/scripts/run.py export
```

Original files stay unchanged. Imported content is marked unverified. Avoid importing session histories, secrets, or company documents whose authority belongs elsewhere. The database now owns imported records; edit through the tool, not the generated export. Open the `human_view` path printed by `export`, or:

Linux:
```sh
xdg-open "$(cat ~/.local/share/argon-knowledge/exports/LATEST.txt)"
```
Windows:
```powershell
Start-Process (Get-Content "$env:LOCALAPPDATA\Argon\Knowledge\exports\LATEST.txt")
```

## Backup, transfer and upgrades

Use `backup /private/new.sqlite3` for a consistent snapshot and `bundle-export /private/new.json` for a revision bundle. Transfer the bundle over an authenticated encrypted channel. On the other device, preview `bundle-import /private/new.json`, repeat with `--apply`, then run `index`. Each machine prepares its model separately. Conflicting edits fail atomically; keep both copies and reconcile deliberately. **There is no background sync.** Never synchronize an open database file.

Before upgrading, back up the store. Install a reviewed release into a new versioned app directory with the same `--data-home` and chosen capture option. The installer updates the skill pointer and keeps its previous version in backups. Read release notes for schema compatibility before opening an existing store with a different version. Keep the Python interpreter used to create the venv installed.

Rollback by restoring the previous skill backup and its `runtime.json`; preserve your data directory. To uninstall, remove the skill and application directory after checking the paths. Keep or separately archive the private data. Nothing needs to be stopped or disabled at boot.

## Data boundaries

Stores, exports, backups and transfer bundles are plaintext under your local OS account; they are not encrypted by this tool. Retrieved excerpts enter your chosen agent's context and are subject to that agent provider's data handling. Local embedding inference does not change that agent boundary. Deleted records remain in history and old snapshots. Do not store credentials. See [the README](../README.md) for record commands and verification details.
