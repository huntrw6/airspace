import json
from pathlib import Path

import pytest

from airspace.entrypoint import ensure_vapid_keys


def test_generates_and_reuses_persistent_vapid_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AIRSPACE_VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("AIRSPACE_VAPID_PRIVATE_KEY", raising=False)
    key_file = tmp_path / "vapid.json"
    first = ensure_vapid_keys(key_file)
    monkeypatch.delenv("AIRSPACE_VAPID_PUBLIC_KEY")
    monkeypatch.delenv("AIRSPACE_VAPID_PRIVATE_KEY")
    second = ensure_vapid_keys(key_file)
    assert first == second
    assert len(first[0]) == 87
    assert len(first[1]) == 43
    assert json.loads(key_file.read_text())["public_key"] == first[0]


def test_rejects_partial_manual_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIRSPACE_VAPID_PUBLIC_KEY", "public-only")
    monkeypatch.delenv("AIRSPACE_VAPID_PRIVATE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Set both"):
        ensure_vapid_keys(tmp_path / "unused.json")
