from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .store import Conflict, KnowledgeError, canonical, digest

FORMAT = "argon-knowledge-git-sync/v1"
CONFIG = "sync.json"


def _command(args, cwd=None, data=None, ok=True, env_updates=None):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(env_updates or {})
    try:
        result = subprocess.run(
            [str(x) for x in args],
            cwd=cwd,
            input=data,
            capture_output=True,
            timeout=120,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise KnowledgeError(f"Command failed to start or timed out: {args[0]}") from exc
    if ok and result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip().splitlines()
        detail = message[-1] if message else f"exit {result.returncode}"
        raise KnowledgeError(f"{Path(str(args[0])).name} failed: {detail}")
    return result


def _tool(name):
    value = shutil.which(name)
    if not value:
        raise KnowledgeError(f"Required executable is unavailable: {name}")
    return value


def _validate_repository(repository):
    if not repository or "\n" in repository or "\r" in repository:
        raise KnowledgeError("Invalid Git repository location.")
    parsed = urlsplit(repository)
    if parsed.scheme and (parsed.username or parsed.password):
        raise KnowledgeError("Do not embed credentials in the Git repository URL.")


def _validate_branch(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,119}", value) or any(
        part in value for part in ["..", "//", "@{", "\\"]
    ):
        raise KnowledgeError("Invalid Git branch name.")


def _validate_device(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
        raise KnowledgeError("Device label must use letters, numbers, dot, underscore, or hyphen.")


def _config_path(home):
    return Path(home).expanduser().absolute() / CONFIG


def _git_environment(ssh_key):
    if not ssh_key:
        return {}
    value = Path(ssh_key).expanduser().absolute()
    if not value.is_file() or value.is_symlink():
        raise KnowledgeError("Git SSH key must be an existing regular file, not a symlink.")
    key = value.as_posix()
    if any(x in key for x in ['"', "\n", "\r"]):
        raise KnowledgeError("Git SSH key path contains unsupported characters.")
    return {"GIT_SSH_COMMAND": f'ssh -i "{key}" -o IdentitiesOnly=yes'}


def _recipient_group(recipients):
    return digest(sorted(recipients))[:16]


def _validate_crypto(age, identity, recipients):
    if not recipients or any(
        not isinstance(x, str) or not re.fullmatch(r"age1[0-9a-z]{20,100}", x)
        for x in recipients
    ):
        raise KnowledgeError("Provide at least one native age recipient.")
    recipients = sorted(set(recipients))
    args = [age, "--encrypt"]
    for recipient in recipients:
        args.extend(["--recipient", recipient])
    encrypted = _command(args, data=b"argon-knowledge-sync-enrollment\n").stdout
    decrypted = _command([age, "--decrypt", "--identity", identity], data=encrypted).stdout
    if decrypted != b"argon-knowledge-sync-enrollment\n":
        raise KnowledgeError("The age identity cannot decrypt for the configured recipients.")
    return recipients


def _write_config(path, value, exclusive=False):
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        if exclusive and path.exists():
            raise KnowledgeError("Git sync is already enrolled on this device.")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load(home):
    path = _config_path(home)
    if not path.is_file() or path.is_symlink():
        raise KnowledgeError("Git sync is not enrolled on this device.")
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "format",
        "repository",
        "branch",
        "device",
        "identity",
        "recipients",
        "checkout",
        "git",
        "age",
    }
    if isinstance(value, dict) and set(value) == required:
        value["ssh_key"] = ""
    elif isinstance(value, dict):
        required.add("ssh_key")
    if not isinstance(value, dict) or set(value) != required or value["format"] != FORMAT:
        raise KnowledgeError("Invalid Git sync configuration.")
    _git_environment(value["ssh_key"])
    return value


def _has_ref(git, checkout, ref):
    return _command([git, "rev-parse", "--verify", "--quiet", ref], checkout, ok=False).returncode == 0


def enroll(home, repository, branch, device, identity, recipients, checkout=None, ssh_key=None):
    home = Path(home).expanduser().absolute()
    path = _config_path(home)
    if path.exists():
        raise KnowledgeError("Git sync is already enrolled on this device.")
    _validate_repository(repository)
    _validate_branch(branch)
    _validate_device(device)
    identity = Path(identity).expanduser().absolute()
    if not identity.is_file() or identity.is_symlink():
        raise KnowledgeError("Age identity must be an existing regular file, not a symlink.")
    git = _tool("git")
    age = _tool("age")
    recipients = _validate_crypto(age, identity, recipients)
    git_environment = _git_environment(ssh_key)

    checkout = (
        Path(checkout).expanduser().absolute() if checkout else home / "sync" / "repository"
    )
    if checkout.exists():
        raise KnowledgeError("Sync checkout already exists; choose a new dedicated path.")
    checkout.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        _command([git, "clone", repository, checkout], env_updates=git_environment)
        remote_ref = f"refs/remotes/origin/{branch}"
        if _has_ref(git, checkout, remote_ref):
            _command([git, "checkout", "-B", branch, f"origin/{branch}"], checkout)
        elif _has_ref(git, checkout, "HEAD"):
            raise KnowledgeError(f"Remote branch does not exist: {branch}")
        else:
            _command([git, "checkout", "--orphan", branch], checkout)
    except BaseException:
        if checkout.exists():
            shutil.rmtree(checkout)
        raise

    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = {
        "format": FORMAT,
        "repository": repository,
        "branch": branch,
        "device": device,
        "identity": str(identity),
        "recipients": recipients,
        "checkout": str(checkout),
        "git": git,
        "age": age,
        "ssh_key": str(Path(ssh_key).expanduser().absolute()) if ssh_key else "",
    }
    _write_config(path, config, exclusive=True)
    return {
        "enrolled": True,
        "repository": repository,
        "branch": branch,
        "device": device,
        "checkout": str(checkout),
        "recipients": len(recipients),
        "recipient_group": _recipient_group(recipients),
    }


def set_recipients(home, recipients):
    path = _config_path(home)
    config = load(home)
    config["recipients"] = _validate_crypto(
        config["age"], config["identity"], recipients
    )
    _write_config(path, config)
    return {
        "updated": True,
        "recipients": len(config["recipients"]),
        "recipient_group": _recipient_group(config["recipients"]),
        "next": "Run sync on this device before enrolling a newly added device.",
    }


def status(home):
    value = load(home)
    checkout = Path(value["checkout"])
    group = _recipient_group(value["recipients"])
    return {
        "enrolled": True,
        "repository": value["repository"],
        "branch": value["branch"],
        "device": value["device"],
        "checkout": str(checkout),
        "checkout_present": (checkout / ".git").is_dir(),
        "recipient_group": group,
        "encrypted_snapshots": len(
            list(checkout.glob(f"snapshots/{group}/*/*.json.age"))
        ),
        "all_encrypted_snapshots": len(list(checkout.glob("snapshots/*/*/*.json.age"))),
        "recipients": len(value["recipients"]),
    }


def _update_checkout(config):
    git = config["git"]
    checkout = Path(config["checkout"])
    branch = config["branch"]
    if not (checkout / ".git").is_dir():
        raise KnowledgeError("The enrolled Git checkout is missing or invalid.")
    if _command([git, "status", "--porcelain"], checkout).stdout.strip():
        raise KnowledgeError("The dedicated sync checkout has uncommitted changes.")
    branch_now = _command([git, "branch", "--show-current"], checkout).stdout.decode().strip()
    if branch_now != branch:
        raise KnowledgeError(f"The dedicated sync checkout must remain on branch {branch}.")
    for key in ["user.name", "user.email"]:
        if not _command([git, "config", "--get", key], checkout, ok=False).stdout.strip():
            raise KnowledgeError(f"Configure Git {key} before syncing.")
    _command([git, "fetch", "origin"], checkout, env_updates=_git_environment(config["ssh_key"]))
    remote_ref = f"refs/remotes/origin/{branch}"
    if _has_ref(git, checkout, remote_ref):
        if _has_ref(git, checkout, "HEAD"):
            _command([git, "rebase", f"origin/{branch}"], checkout)
        else:
            _command([git, "checkout", "-B", branch, f"origin/{branch}"], checkout)


def _decrypt_bundles(config):
    checkout = Path(config["checkout"])
    bundles = []
    group = _recipient_group(config["recipients"])
    for path in sorted(checkout.glob(f"snapshots/{group}/*/*.json.age")):
        data = _command(
            [config["age"], "--decrypt", "--identity", config["identity"], path]
        ).stdout
        try:
            bundles.append((path, json.loads(data)))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KnowledgeError(f"Invalid decrypted bundle: {path.relative_to(checkout)}") from exc
    return bundles


def _write_snapshot(config, bundle):
    checkout = Path(config["checkout"])
    raw = (canonical(bundle) + "\n").encode()
    bundle_hash = digest(bundle)
    relative = (
        Path("snapshots")
        / _recipient_group(config["recipients"])
        / config["device"]
        / f"{bundle_hash}.json.age"
    )
    target = checkout / relative
    if target.exists():
        return relative, bundle_hash, False
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{uuid.uuid4().hex}.tmp"
    args = [config["age"], "--encrypt", "--output", temporary]
    for recipient in config["recipients"]:
        args.extend(["--recipient", recipient])
    try:
        _command(args, data=raw)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return relative, bundle_hash, True


def synchronize(home, store, attempts=3):
    config = load(home)
    git = config["git"]
    checkout = Path(config["checkout"])
    imported = set()
    published = False
    last_push = None
    for _ in range(attempts):
        _update_checkout(config)
        bundles = _decrypt_bundles(config)
        with store.transaction():
            for path, bundle in bundles:
                result = store.merge(bundle, apply=True)
                if result["records_to_update"]:
                    imported.update(result["record_ids"])
        relative, bundle_hash, created = _write_snapshot(config, store.bundle())
        if created:
            try:
                _command([git, "add", "--", relative], checkout)
                _command(
                    [git, "commit", "-m", f"sync: {config['device']} {bundle_hash[:12]}"],
                    checkout,
                )
            except BaseException:
                _command([git, "rm", "--cached", "--ignore-unmatch", "--", relative], checkout, ok=False)
                (checkout / relative).unlink(missing_ok=True)
                raise
            published = True
        last_push = _command(
            [git, "push", "origin", f"HEAD:refs/heads/{config['branch']}"],
            checkout,
            ok=False,
            env_updates=_git_environment(config["ssh_key"]),
        )
        if last_push.returncode == 0:
            return {
                "synchronized": True,
                "device": config["device"],
                "imported_records": len(imported),
                "imported_record_ids": sorted(imported),
                "snapshot": str(relative).replace("\\", "/"),
                "bundle_hash": bundle_hash,
                "recipient_group": _recipient_group(config["recipients"]),
                "published": published,
                "attempts": _ + 1,
            }
    detail = last_push.stderr.decode("utf-8", "replace").strip().splitlines()
    raise Conflict(
        "Git sync could not publish after concurrent updates"
        + (f": {detail[-1]}" if detail else ".")
    )
