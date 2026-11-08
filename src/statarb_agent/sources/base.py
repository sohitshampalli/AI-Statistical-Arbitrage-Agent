"""Common source interface, snapshot store and manifest.

Every data source (prices now; filings, news and FRED later) follows one
pattern:

- `fetch` downloads once and writes an immutable snapshot under
  data/raw/<source>/<key>/, then records it in data/manifest.json.
- `load` reads only the cache, never the network, verifies the snapshot, and
  returns only items dated strictly before `asof`.

A snapshot is never appended to or edited. Refreshing writes a new snapshot,
so rows from two downloads of the same key can never be mixed by accident.

Each manifest entry records two hashes, both checked on every read:
- file_sha256: SHA-256 of the Parquet file bytes.
- content_sha256: SHA-256 over the column names, dtypes, index name and
  pandas.util.hash_pandas_object of the data. It identifies the data itself,
  independent of how the file was written.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final, Protocol

import pandas as pd

from statarb_agent.provenance import code_version

SCHEMA_VERSION: Final = 1
MANIFEST_NAME: Final = "manifest.json"
RAW_DIR: Final = "raw"

_SOURCE_NAME: Final = re.compile(r"[a-z][a-z0-9_]{0,31}")
_KEY: Final = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
_KEY_MAX: Final = 32


class NotCachedError(LookupError):
    """No snapshot exists for the requested source and key."""


class CacheIntegrityError(RuntimeError):
    """A snapshot file does not match the hashes recorded in the manifest."""


@dataclass(frozen=True)
class ManifestEntry:
    """One immutable snapshot, as recorded in the manifest.

    Attributes:
        snapshot_id: "<source>/<key>/<UTC timestamp>", unique.
        source: Source name, for example "yfinance".
        source_version: Version of the client library used to download.
        kind: What the snapshot holds, for example "prices_daily".
        key: Normalised key, for example a ticker in Yahoo's form.
        url: Endpoint the data came from.
        request: Every parameter sent with the request.
        retrieved_at_utc: ISO 8601 UTC time of the download.
        path: File path relative to the data folder.
        file_sha256: SHA-256 of the file bytes.
        content_sha256: SHA-256 of the data (see module docstring).
        n_bytes: File size.
        n_rows: Number of rows.
        columns: Column names in order.
        first_date: First index date (ISO), if the index is a DatetimeIndex.
        last_date: Last index date (ISO), if the index is a DatetimeIndex.
        pandas_version: pandas version that computed content_sha256.
        pyarrow_version: pyarrow version that wrote the file.
        code_commit: Git HEAD of this repository at download time.
        code_dirty: Whether tracked files had uncommitted changes.
        notes: Free-text remarks from the source, for example clipping.
        schema_version: Manifest schema version.
    """

    snapshot_id: str
    source: str
    source_version: str
    kind: str
    key: str
    url: str
    request: Mapping[str, Any]
    retrieved_at_utc: str
    path: str
    file_sha256: str
    content_sha256: str
    n_bytes: int
    n_rows: int
    columns: tuple[str, ...]
    first_date: str | None
    last_date: str | None
    pandas_version: str
    pyarrow_version: str
    code_commit: str
    code_dirty: bool
    notes: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = SCHEMA_VERSION

    def to_json(self) -> dict[str, Any]:
        """Plain JSON-ready dict (tuples become lists)."""
        out = asdict(self)
        out["request"] = dict(self.request)
        out["columns"] = list(self.columns)
        out["notes"] = list(self.notes)
        return out

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> ManifestEntry:
        """Inverse of to_json. Raises ValueError on unknown or missing fields."""
        names = set(cls.__dataclass_fields__)
        if set(raw) != names:
            extra, missing = set(raw) - names, names - set(raw)
            raise ValueError(f"bad manifest entry: extra {extra}, missing {missing}")
        data = dict(raw)
        data["request"] = dict(data["request"])
        data["columns"] = tuple(data["columns"])
        data["notes"] = tuple(data["notes"])
        return cls(**data)


def validate_source_name(name: str) -> str:
    """Source names are lowercase identifiers, used as a folder name."""
    if not isinstance(name, str) or not _SOURCE_NAME.fullmatch(name):
        raise ValueError(f"invalid source name {name!r}")
    return name


def validate_key(key: str) -> str:
    """Keys are already normalised: uppercase letters and digits joined by '-'.

    The store only accepts keys in this form, so a key can never contain a
    path separator or "..". Sources normalise user input first (for prices,
    with normalise_ticker).
    """
    if not isinstance(key, str) or len(key) > _KEY_MAX or not _KEY.fullmatch(key):
        raise ValueError(f"invalid key {key!r}: normalise it before storing")
    return key


def content_sha256(frame: pd.DataFrame) -> str:
    """Hash of the data in `frame`, independent of the file it came from.

    Covers column names and dtypes, the index name and dtype, and every value
    and index label via pandas.util.hash_pandas_object. hash_pandas_object
    alone ignores column names, so they are hashed separately. The result can
    change across pandas versions, so the manifest records pandas_version.
    """
    digest = hashlib.sha256()
    header = {
        "columns": [str(c) for c in frame.columns],
        "dtypes": [str(t) for t in frame.dtypes],
        "index_name": frame.index.name,
        "index_dtype": str(frame.index.dtype),
    }
    digest.update(json.dumps(header, sort_keys=True).encode())
    rows = pd.util.hash_pandas_object(frame, index=True).to_numpy()
    digest.update(rows.tobytes())
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _iso_date(value: Any) -> str:
    return pd.Timestamp(value).isoformat()


class Manifest:
    """Index of every snapshot, stored as one JSON file.

    Writes go to a temporary file in the same folder and replace the manifest
    in one os.replace call, so an interrupted write leaves the old manifest
    intact.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def entries(
        self, *, source: str | None = None, key: str | None = None
    ) -> list[ManifestEntry]:
        """All entries in the order they were added, optionally filtered."""
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text())
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported manifest schema in {self.path}")
        out = [ManifestEntry.from_json(e) for e in raw["entries"]]
        return [
            e
            for e in out
            if (source is None or e.source == source) and (key is None or e.key == key)
        ]

    def append(self, entry: ManifestEntry) -> None:
        """Add an entry. Raises ValueError if its snapshot_id already exists."""
        current = self.entries()
        if any(e.snapshot_id == entry.snapshot_id for e in current):
            raise ValueError(f"snapshot {entry.snapshot_id} is already in the manifest")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "entries": [e.to_json() for e in [*current, entry]],
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".manifest-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(text)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, snapshot_id: str) -> ManifestEntry:
        """Entry with this snapshot_id. Raises NotCachedError if absent."""
        for entry in self.entries():
            if entry.snapshot_id == snapshot_id:
                return entry
        raise NotCachedError(f"no snapshot {snapshot_id!r} in {self.path}")

    def latest(self, source: str, key: str) -> ManifestEntry:
        """Most recently retrieved snapshot for (source, key)."""
        found = self.entries(source=source, key=key)
        if not found:
            raise NotCachedError(f"no cached {source} data for {key}")
        return max(found, key=lambda e: e.retrieved_at_utc)


class SnapshotStore:
    """Writes immutable Parquet snapshots and reads them back verified.

    Files live at <root>/raw/<source>/<key>/<UTC timestamp>.parquet and the
    manifest at <root>/manifest.json, where root is normally data/.
    """

    def __init__(self, root: Path, *, repo_root: Path) -> None:
        self.root = Path(root)
        self.repo_root = Path(repo_root)
        self.manifest = Manifest(self.root / MANIFEST_NAME)

    def _resolve(self, relative: str) -> Path:
        """Absolute path of a manifest path, refusing anything outside raw/."""
        raw_dir = (self.root / RAW_DIR).resolve()
        path = (self.root / relative).resolve()
        if not path.is_relative_to(raw_dir):
            raise CacheIntegrityError(f"snapshot path {relative!r} is outside {raw_dir}")
        return path

    def write(
        self,
        *,
        source: str,
        source_version: str,
        kind: str,
        key: str,
        url: str,
        request: Mapping[str, Any],
        frame: pd.DataFrame,
        retrieved_at: pd.Timestamp,
        notes: tuple[str, ...] = (),
    ) -> ManifestEntry:
        """Write `frame` as a new snapshot and record it in the manifest.

        Raises:
            ValueError: On an invalid source name or key, an empty frame, or a
                timezone-naive `retrieved_at`.
            TypeError: If `request` is not JSON-serialisable.
            FileExistsError: If a snapshot with the same timestamp exists.
            CacheIntegrityError: If the Parquet round trip changes the data.
        """
        validate_source_name(source)
        validate_key(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise ValueError("refusing to store an empty snapshot")
        stamp = pd.Timestamp(retrieved_at)
        if stamp.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        stamp = stamp.tz_convert("UTC")
        request = dict(request)
        json.dumps(request)  # TypeError if not serialisable

        version = code_version(self.repo_root)
        name = stamp.strftime("%Y%m%dT%H%M%S%fZ")
        relative = f"{RAW_DIR}/{source}/{key}/{name}.parquet"
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as fh:  # never overwrite
            frame.to_parquet(fh, engine="pyarrow", index=True)

        back = pd.read_parquet(path, engine="pyarrow")
        content = content_sha256(back)
        if content != content_sha256(frame):
            path.unlink()
            raise CacheIntegrityError("Parquet round trip changed the data")

        is_dated = isinstance(frame.index, pd.DatetimeIndex)
        entry = ManifestEntry(
            snapshot_id=f"{source}/{key}/{name}",
            source=source,
            source_version=source_version,
            kind=kind,
            key=key,
            url=url,
            request=request,
            retrieved_at_utc=stamp.isoformat(),
            path=relative,
            file_sha256=_file_sha256(path),
            content_sha256=content,
            n_bytes=path.stat().st_size,
            n_rows=len(frame),
            columns=tuple(str(c) for c in frame.columns),
            first_date=_iso_date(frame.index.min()) if is_dated else None,
            last_date=_iso_date(frame.index.max()) if is_dated else None,
            pandas_version=pd.__version__,
            pyarrow_version=importlib.metadata.version("pyarrow"),
            code_commit=version.commit,
            code_dirty=version.dirty,
            notes=tuple(notes),
        )
        try:
            self.manifest.append(entry)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return entry

    def read(self, entry: ManifestEntry) -> pd.DataFrame:
        """Read a snapshot, verifying the file hash and then the content hash.

        Raises:
            CacheIntegrityError: If the path is outside raw/, the file is
                missing, or either hash differs from the manifest.
        """
        path = self._resolve(entry.path)
        if not path.is_file():
            raise CacheIntegrityError(f"snapshot file missing: {entry.path}")
        if _file_sha256(path) != entry.file_sha256:
            raise CacheIntegrityError(f"file hash mismatch for {entry.snapshot_id}")
        frame = pd.read_parquet(path, engine="pyarrow")
        if content_sha256(frame) != entry.content_sha256:
            raise CacheIntegrityError(f"content hash mismatch for {entry.snapshot_id}")
        return frame


class Source[RequestT, ItemT](Protocol):
    """Interface every data source follows.

    `fetch` is the only method that may use the network. `load` reads the
    cache only and returns items dated strictly before `asof`.
    """

    name: ClassVar[str]

    def fetch(self, request: RequestT) -> ManifestEntry: ...

    def load(
        self,
        key: str,
        *,
        asof: pd.Timestamp | str,
        start: pd.Timestamp | str | None = None,
        snapshot_id: str | None = None,
    ) -> ItemT: ...
