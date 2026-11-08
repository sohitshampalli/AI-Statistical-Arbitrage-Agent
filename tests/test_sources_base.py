"""Tests for ticker validation, the snapshot store and the manifest.

The store has no `asof`: it returns whole snapshots and estimates nothing.
Look-ahead tests belong to each source's `load` (commit 3 for prices).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statarb_agent.provenance import code_version
from statarb_agent.sources.base import (
    CacheIntegrityError,
    Manifest,
    ManifestEntry,
    NotCachedError,
    SnapshotMissingError,
    SnapshotStore,
    content_sha256,
    validate_key,
    validate_source_name,
)
from statarb_agent.sources.tickers import normalise_ticker

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = pd.Timestamp("2026-11-08 10:15:00.123456", tz="UTC")


def _frame(n: int = 5, start: str = "2010-01-04") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=n, name="date")
    return pd.DataFrame(
        {
            "close": np.linspace(10.0, 11.0, n),
            "volume": np.arange(n, dtype="int64") * 100,
        },
        index=idx,
    )


def _write(
    store: SnapshotStore,
    frame: pd.DataFrame | None = None,
    *,
    key: str = "KO",
    at: pd.Timestamp = T0,
) -> ManifestEntry:
    return store.write(
        source="yfinance",
        source_version="1.8.0",
        kind="prices_daily",
        key=key,
        url="https://example.invalid/chart/KO",
        request={"start": "2010-01-01", "end": "2022-01-01", "repair": False},
        frame=_frame() if frame is None else frame,
        retrieved_at=at,
    )


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "data", repo_root=REPO_ROOT)


# Tickers -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("KO", "KO"),
        ("SPY", "SPY"),
        ("BRK.B", "BRK-B"),
        ("BRK-B", "BRK-B"),
        ("BF.B", "BF-B"),
        ("A", "A"),
        ("1234", "1234"),
        ("ABCDEFGHIJKL", "ABCDEFGHIJKL"),  # 12 characters, the maximum
        ("ko", "KO"),
        ("brk.b", "BRK-B"),
        ("Brk.B", "BRK-B"),
        ("bRk-b", "BRK-B"),
        ("spy", "SPY"),
    ],
)
def test_valid_tickers(raw: str, expected: str) -> None:
    assert normalise_ticker(raw) == expected
    assert validate_key(normalise_ticker(raw)) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " KO",
        " ko",
        "KO ",
        "K O",
        "KO\n",
        "KO\x00",
        "..",
        ".",
        "../KO",
        "KO/..",
        "../../etc/passwd",
        "A/B",
        "A\\B",
        "/KO",
        "~KO",
        "^GSPC",
        "BRK..B",
        "BRK.-B",
        "-KO",
        "KO-",
        ".KO",
        "KO.",
        "KO;rm",
        "KO*",
        "\uff2b\uff2f",  # fullwidth K and O
        "K\u039f",  # Greek capital omicron that looks like O
        "\u0131bm",  # dotless i, which uppercases to ASCII I
        "\u017fpy",  # long s, which uppercases to ASCII S
        "k\u00f6",  # o with diaeresis
        "brk..b",
        "../ko",
        "ABCDEFGHIJKLM",  # 13 characters
    ],
    ids=repr,
)
def test_invalid_tickers_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid ticker"):
        normalise_ticker(raw)


@pytest.mark.parametrize("raw", [None, 123, b"KO", ["KO"]], ids=repr)
def test_non_string_tickers_raise_type_error(raw: object) -> None:
    with pytest.raises(TypeError):
        normalise_ticker(raw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "key", ["BRK.B", "ko", "../KO", "KO/X", "", "..", "A" * 33, "KO-"], ids=repr
)
def test_store_rejects_keys_that_are_not_normalised(
    store: SnapshotStore, key: str
) -> None:
    with pytest.raises(ValueError, match="invalid key"):
        _write(store, key=key)
    assert not (store.root / "raw").exists()


@pytest.mark.parametrize("name", ["../yf", "YF", "y f", "", "yf/x", "1yf"], ids=repr)
def test_invalid_source_names(name: str) -> None:
    with pytest.raises(ValueError):
        validate_source_name(name)


# Content hash ------------------------------------------------------------


def test_content_hash_ignores_file_but_sees_every_change() -> None:
    base = _frame()
    h = content_sha256(base)
    assert h == content_sha256(base.copy())
    assert len(h) == 64
    changed_value = base.copy()
    changed_value.iloc[2, 0] += 1e-9
    changed_index = base.copy()
    changed_index.index = changed_index.index + pd.Timedelta(days=1)
    variants = [
        changed_value,
        base.rename(columns={"close": "adj_close"}),
        base.astype({"volume": "float64"}),
        changed_index,
        base.rename_axis("day"),
        base[["volume", "close"]],
        base.iloc[:-1],
    ]
    for variant in variants:
        assert content_sha256(variant) != h


# Store round trip and integrity -------------------------------------------


def test_write_then_read_round_trip(store: SnapshotStore) -> None:
    frame = _frame()
    entry = _write(store, frame)
    assert entry.snapshot_id == "yfinance/KO/20261108T101500123456Z"
    assert entry.path == "raw/yfinance/KO/20261108T101500123456Z.parquet"
    assert entry.retrieved_at_utc == "2026-11-08T10:15:00.123456+00:00"
    assert entry.n_rows == 5 and entry.columns == ("close", "volume")
    assert entry.first_date == "2010-01-04T00:00:00"
    assert entry.last_date == "2010-01-08T00:00:00"
    assert len(entry.file_sha256) == 64 and entry.content_sha256 == content_sha256(frame)
    assert entry.n_bytes == (store.root / entry.path).stat().st_size
    assert entry.pandas_version == pd.__version__
    pd.testing.assert_frame_equal(
        store.read(entry), frame, check_exact=True, check_freq=False
    )


def test_manifest_persists_and_matches_entry(store: SnapshotStore) -> None:
    entry = _write(store)
    reloaded = Manifest(store.root / "manifest.json")
    assert reloaded.entries() == [entry]
    assert reloaded.get(entry.snapshot_id) == entry
    raw = json.loads((store.root / "manifest.json").read_text())
    assert raw["schema_version"] == 1 and len(raw["entries"]) == 1


def test_tampered_file_is_detected(store: SnapshotStore) -> None:
    entry = _write(store)
    path = store.root / entry.path
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(CacheIntegrityError, match="file hash"):
        store.read(entry)


def test_changed_content_is_detected_even_with_matching_file_hash(
    store: SnapshotStore,
) -> None:
    entry = _write(store)
    path = store.root / entry.path
    edited = _frame()
    edited.iloc[0, 0] = 999.0
    edited.to_parquet(path, engine="pyarrow", index=True)
    forged = dataclasses.replace(
        entry, file_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(CacheIntegrityError, match="content hash"):
        store.read(forged)


def test_non_ascii_is_rejected_before_uppercasing() -> None:
    assert "\u0131".upper() == "I" and "\u017f".upper() == "S"  # why order matters
    for raw in ("\u0131BM", "\u017fPY"):
        with pytest.raises(ValueError, match="only ASCII"):
            normalise_ticker(raw)


def test_missing_file_in_fresh_clone_names_key_snapshot_and_fix(
    store: SnapshotStore,
) -> None:
    entry = _write(store)
    (store.root / entry.path).unlink()  # what a fresh clone looks like
    with pytest.raises(SnapshotMissingError) as info:
        store.read(entry)
    message = str(info.value)
    assert "KO" in message
    assert entry.snapshot_id in message
    assert "statarb fetch KO" in message
    assert isinstance(info.value, NotCachedError)


@pytest.mark.parametrize(
    "path",
    ["../../outside.parquet", "/etc/passwd", "manifest.json", "raw/../manifest.json"],
)
def test_manifest_paths_outside_raw_are_refused(
    store: SnapshotStore, path: str
) -> None:
    entry = _write(store)
    with pytest.raises(CacheIntegrityError, match="outside"):
        store.read(dataclasses.replace(entry, path=path))


def test_snapshots_are_never_overwritten(store: SnapshotStore) -> None:
    first = _write(store)
    with pytest.raises(FileExistsError):
        _write(store, _frame(n=7))
    pd.testing.assert_frame_equal(
        store.read(first), _frame(), check_exact=True, check_freq=False
    )
    assert len(store.manifest.entries()) == 1


def test_latest_returns_newest_snapshot(store: SnapshotStore) -> None:
    old = _write(store, _frame(n=5), at=T0)
    new = _write(store, _frame(n=6), at=T0 + pd.Timedelta(days=1))
    _write(store, _frame(n=4), key="PEP", at=T0 + pd.Timedelta(days=2))
    assert store.manifest.latest("yfinance", "KO") == new
    assert store.manifest.entries(key="KO") == [old, new]
    with pytest.raises(NotCachedError):
        store.manifest.latest("yfinance", "XOM")
    with pytest.raises(NotCachedError):
        store.manifest.get("yfinance/XOM/20260101T000000000000Z")


def test_retrieved_at_is_stored_in_utc(store: SnapshotStore) -> None:
    eastern = pd.Timestamp("2026-11-08 05:15:00", tz="America/New_York")
    entry = _write(store, at=eastern)
    assert entry.retrieved_at_utc == "2026-11-08T10:15:00+00:00"


@pytest.mark.parametrize(
    "bad",
    [
        {"frame": pd.DataFrame({"close": []})},
        {"retrieved_at": pd.Timestamp("2026-11-08 10:15")},  # naive
        {"request": {"when": pd.Timestamp("2010-01-01")}},  # not JSON
        {"source": "../yf"},
    ],
    ids=["empty", "naive_time", "request_not_json", "bad_source"],
)
def test_bad_write_arguments(store: SnapshotStore, bad: dict) -> None:
    kwargs = {
        "source": "yfinance",
        "source_version": "1.8.0",
        "kind": "prices_daily",
        "key": "KO",
        "url": "https://example.invalid/",
        "request": {},
        "frame": _frame(),
        "retrieved_at": T0,
    } | bad
    with pytest.raises((ValueError, TypeError)):
        store.write(**kwargs)
    assert store.manifest.entries() == []


def test_interrupted_manifest_write_keeps_old_manifest(
    store: SnapshotStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _write(store)
    before = (store.root / "manifest.json").read_bytes()

    def crash(src: str, dst: str) -> None:
        raise OSError("simulated crash")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError, match="simulated crash"):
        _write(store, at=T0 + pd.Timedelta(hours=1))
    assert (store.root / "manifest.json").read_bytes() == before
    assert store.manifest.entries() == [first]
    leftovers = [p.name for p in store.root.rglob("*") if p.is_file()]
    assert sorted(leftovers) == sorted(["manifest.json", Path(first.path).name])


def test_manifest_rejects_duplicate_ids_and_unknown_fields(
    store: SnapshotStore,
) -> None:
    entry = _write(store)
    with pytest.raises(ValueError, match="already"):
        store.manifest.append(entry)
    raw = entry.to_json() | {"surprise": 1}
    with pytest.raises(ValueError, match="extra"):
        ManifestEntry.from_json(raw)


def test_manifest_round_trips_through_json(store: SnapshotStore) -> None:
    entry = _write(store)
    assert ManifestEntry.from_json(json.loads(json.dumps(entry.to_json()))) == entry


# Provenance and git ignore rules ------------------------------------------


def test_code_version_in_a_throwaway_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
             "-c", "commit.gpgsign=false", *args],
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    (repo / "f.txt").write_text("a\n")
    git("add", "f.txt")
    git("commit", "-q", "-m", "c")
    clean = code_version(repo)
    assert len(clean.commit) == 40 and clean.dirty is False
    (repo / "untracked.txt").write_text("x\n")
    assert code_version(repo).dirty is False  # untracked files do not count
    (repo / "f.txt").write_text("b\n")
    assert code_version(repo) == dataclasses.replace(clean, dirty=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    assert code_version(plain).commit == "unknown"


def _ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", path], check=False
    )
    return result.returncode == 0


def test_only_the_manifest_in_data_can_be_committed() -> None:
    assert _ignored("data/raw/yfinance/KO/20261108T101500000000Z.parquet")
    assert _ignored("data/cache/yfinance/tkr-tz.db")
    assert _ignored("data/other.json")
    assert not _ignored("data/manifest.json")
    assert not _ignored("src/statarb_agent/data/synthetic.py")
