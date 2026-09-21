import json
import shutil
import subprocess

import pytest

from argon_knowledge import sync
from argon_knowledge.store import Conflict, Store, record_id
from argon_knowledge.sync import enroll, set_recipients, status, synchronize


def payload(body):
    return {
        "scope": "personal",
        "kind": "fact",
        "title": "Synchronized knowledge",
        "body": body,
        "source": "test:git-sync",
        "source_revision": "",
        "tags": ["sync-test"],
        "verification": "verified",
        "status": "active",
    }


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def configure_git(home):
    config = json.loads((home / "sync.json").read_text())
    checkout = config["checkout"]
    run("git", "config", "user.name", "Agentic Knowledge Test", cwd=checkout)
    run("git", "config", "user.email", "agentic-knowledge@example.invalid", cwd=checkout)


@pytest.mark.skipif(
    not all(shutil.which(x) for x in ["age", "age-keygen", "git"]),
    reason="age and Git are required",
)
def test_encrypted_git_sync_and_divergence(tmp_path):
    identity = tmp_path / "identity.txt"
    run("age-keygen", "-o", str(identity))
    recipient = run("age-keygen", "-y", str(identity)).stdout.strip()
    remote = tmp_path / "knowledge.git"
    run("git", "init", "--bare", "--initial-branch=main", str(remote))

    home_a = tmp_path / "device-a"
    home_b = tmp_path / "device-b"
    store_a = Store(home_a / "knowledge.sqlite3", create=True)
    store_b = Store(home_b / "knowledge.sqlite3", create=True)
    try:
        enroll(home_a, str(remote), "main", "device-a", identity, [recipient])
        configure_git(home_a)
        first_id = record_id("personal", "first")
        first = store_a.put(first_id, payload("Private synchronized value"))
        first_sync = synchronize(home_a, store_a)
        assert first_sync["published"]
        assert status(home_a)["encrypted_snapshots"] == 1
        encrypted = next((home_a / "sync/repository/snapshots").rglob("*.age")).read_bytes()
        assert b"Private synchronized value" not in encrypted

        enroll(home_b, str(remote), "main", "device-b", identity, [recipient])
        configure_git(home_b)
        imported = synchronize(home_b, store_b)
        assert imported["imported_records"] == 1
        assert imported["index_required"] is True
        assert store_b.get(first_id)["revision"] == first["revision"]

        second_id = record_id("personal", "second")
        store_b.put(second_id, payload("Second device value"))
        synchronize(home_b, store_b)
        assert synchronize(home_a, store_a)["imported_records"] == 1
        assert store_a.get(second_id)["body"] == "Second device value"

        base = store_a.get(first_id)["revision"]
        store_a.put(first_id, payload("Device A fork"), base)
        synchronize(home_a, store_a)
        store_b.put(first_id, payload("Device B fork"), base)
        with pytest.raises(Conflict, match="Divergent record heads"):
            synchronize(home_b, store_b)
        assert store_b.get(first_id)["body"] == "Device B fork"
    finally:
        store_a.close()
        store_b.close()


def test_enrollment_rejects_embedded_credentials(tmp_path):
    store = Store(tmp_path / "home/knowledge.sqlite3", create=True)
    store.close()
    with pytest.raises(Exception, match="credentials"):
        enroll(
            tmp_path / "home",
            "https://token@example.com/private.git",
            "main",
            "device-a",
            tmp_path / "missing-key",
            ["age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"],
        )


def test_status_accepts_config_created_before_ssh_key_support(tmp_path):
    home = tmp_path / "home"
    checkout = home / "sync/repository"
    checkout.mkdir(parents=True)
    (checkout / ".git").mkdir()
    config = {
        "format": "argon-knowledge-git-sync/v1",
        "repository": "https://example.invalid/private.git",
        "branch": "main",
        "device": "device-a",
        "identity": str(tmp_path / "identity.txt"),
        "recipients": ["age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"],
        "checkout": str(checkout),
        "git": "git",
        "age": "age",
    }
    (home / "sync.json").write_text(json.dumps(config))
    assert status(home)["device"] == "device-a"


def test_status_does_not_require_access_to_the_configured_ssh_key(tmp_path, monkeypatch):
    home = tmp_path / "home"
    checkout = home / "sync/repository"
    checkout.mkdir(parents=True)
    (checkout / ".git").mkdir()
    config = {
        "format": "argon-knowledge-git-sync/v1",
        "repository": "git@example.invalid:private.git",
        "branch": "main",
        "device": "device-a",
        "identity": str(tmp_path / "identity.txt"),
        "recipients": ["age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"],
        "checkout": str(checkout),
        "git": "git",
        "age": "age",
        "ssh_key": str(tmp_path / "unreadable-private-key"),
    }
    (home / "sync.json").write_text(json.dumps(config))

    def fail_if_validated(_):
        raise AssertionError("read-only status must not validate the SSH key")

    monkeypatch.setattr(sync, "_git_environment", fail_if_validated)
    assert status(home)["device"] == "device-a"


def test_git_commands_scope_safe_directory_to_the_checkout(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    captured = {}
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")

    def fake_run(args, **kwargs):
        captured.update(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(sync.subprocess, "run", fake_run)
    sync._command(["git", "status", "--porcelain"], checkout)
    assert captured["GIT_CONFIG_COUNT"] == "1"
    assert captured["GIT_CONFIG_KEY_0"] == "safe.directory"
    assert captured["GIT_CONFIG_VALUE_0"] == checkout.absolute().as_posix()


@pytest.mark.skipif(
    not all(shutil.which(x) for x in ["age", "age-keygen", "git"]),
    reason="age and Git are required",
)
def test_new_recipient_group_can_onboard_device(tmp_path):
    old_identity = tmp_path / "old.txt"
    new_identity = tmp_path / "new.txt"
    run("age-keygen", "-o", str(old_identity))
    run("age-keygen", "-o", str(new_identity))
    old_recipient = run("age-keygen", "-y", str(old_identity)).stdout.strip()
    new_recipient = run("age-keygen", "-y", str(new_identity)).stdout.strip()
    remote = tmp_path / "knowledge.git"
    run("git", "init", "--bare", "--initial-branch=main", str(remote))
    home_a = tmp_path / "device-a"
    home_b = tmp_path / "device-b"
    store_a = Store(home_a / "knowledge.sqlite3", create=True)
    store_b = Store(home_b / "knowledge.sqlite3", create=True)
    try:
        enroll(home_a, str(remote), "main", "device-a", old_identity, [old_recipient])
        configure_git(home_a)
        key = record_id("personal", "onboarding")
        store_a.put(key, payload("Available to the new device"))
        synchronize(home_a, store_a)
        old_group = status(home_a)["recipient_group"]

        updated = set_recipients(home_a, [old_recipient, new_recipient])
        assert updated["recipient_group"] != old_group
        synchronize(home_a, store_a)
        enroll(
            home_b,
            str(remote),
            "main",
            "device-b",
            new_identity,
            [old_recipient, new_recipient],
        )
        configure_git(home_b)
        assert synchronize(home_b, store_b)["imported_records"] == 1
        assert store_b.get(key)["body"] == "Available to the new device"
    finally:
        store_a.close()
        store_b.close()
