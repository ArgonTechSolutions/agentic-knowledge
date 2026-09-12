"""Portable skill entrypoint; no service, shell expansion, or implicit installation."""

import json
import subprocess
import sys
from pathlib import Path

config = Path(__file__).resolve().parents[1] / "runtime.json"
if not config.is_file():
    sys.exit("Agentic Knowledge is not configured. Run the tool installer for this machine.")
settings = json.loads(config.read_text(encoding="utf-8"))
if sys.argv[1:] == ["policy"]:
    print(json.dumps({"automatic_capture": settings.get("automatic_capture", False)}))
    sys.exit(0)
raise SystemExit(
    subprocess.call(
        [settings["python"], "-m", "argon_knowledge.cli", "--home", settings["home"], *sys.argv[1:]]
    )
)
