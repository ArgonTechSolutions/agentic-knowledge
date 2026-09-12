import os
from pathlib import Path

import pytest

from argon_knowledge.semantic import index, prepare, search
from argon_knowledge.store import Store, record_id


@pytest.mark.skipif(not os.environ.get("ARGON_TEST_MODEL"), reason="Local model not supplied")
def test_real_multilingual_retrieval(tmp_path):
    home = tmp_path / "private"
    store = Store(home / "knowledge.sqlite3", create=True)
    try:
        prepare(home, Path(os.environ["ARGON_TEST_MODEL"]))
        for key, title, body in [
            (
                "quiet",
                "On-demand tools",
                "Run knowledge commands only when needed. Do not keep a background service or model resident in RAM.",
            ),
            ("food", "Food preference", "I enjoy cooking Italian pasta with fresh tomatoes."),
            (
                "privacy",
                "Knowledge privacy",
                "Personal knowledge remains private to its owner. Each installation uses its own separate data.",
            ),
        ]:
            store.put(
                record_id("personal", key),
                dict(
                    scope="personal",
                    kind="preference",
                    title=title,
                    body=body,
                    source="synthetic:test",
                    source_revision="",
                    tags=[],
                    verification="reported",
                    status="active",
                ),
            )
        assert index(store, home)["indexed"] == 3
        for query, expected in [
            (
                "No quiero procesos consumiendo memoria cuando no estoy usando la herramienta",
                "quiet",
            ),
            ("Can my colleagues read my personal notes?", "privacy"),
        ]:
            result = search(store, home, query, mode="semantic")["results"]
            assert result and result[0]["id"] == record_id("personal", expected)
        assert not search(store, home, "What is the orbital period of Neptune?", mode="semantic")[
            "results"
        ]
        assert index(store, home)["indexed"] == 0
    finally:
        store.close()
