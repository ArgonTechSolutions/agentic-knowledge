"""Explicit local installer. Never starts services or imports personal knowledge."""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--app-dir", required=True, type=Path)
p.add_argument("--data-home", required=True, type=Path)
p.add_argument(
    "--codex-home",
    type=Path,
    default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
)
p.add_argument("--semantic", action="store_true")
p.add_argument(
    "--automatic-capture",
    action="store_true",
    help="Authorize selected durable automatic saves for this owner",
)
a = p.parse_args()
source = Path(__file__).resolve().parents[1]
app = a.app_dir.expanduser().absolute()
if app.exists():
    sys.exit(
        "App directory already exists; choose a new versioned directory. Existing data stays intact."
    )
shutil.copytree(
    source,
    app,
    ignore=shutil.ignore_patterns(
        ".git", ".venv", "__pycache__", "*.egg-info", ".pytest_cache", ".ruff_cache"
    ),
)
venv.EnvBuilder(with_pip=True).create(app / ".venv")
python = app / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
subprocess.run(
    [str(python), "-m", "pip", "install", str(app) + ("[semantic]" if a.semantic else "")],
    check=True,
)
home = a.data_home.expanduser().absolute()
subprocess.run([str(python), "-m", "argon_knowledge.cli", "--home", str(home), "init"], check=True)
skill = a.codex_home.expanduser() / "skills/agentic-knowledge"
if skill.exists():
    backup = (
        a.codex_home.expanduser()
        / "backups"
        / ("agentic-knowledge-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"))
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill, backup)
    shutil.rmtree(skill)
shutil.copytree(app / "skills/agentic-knowledge", skill)
(skill / "runtime.json").write_text(
    json.dumps(
        {"python": str(python), "home": str(home), "automatic_capture": a.automatic_capture},
        indent=2,
    ),
    encoding="utf-8",
)
print(json.dumps({"app": str(app), "home": str(home), "skill": str(skill)}))
