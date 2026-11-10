"""Which code and configs produced a result.

code_version gives the git commit and whether the tree was dirty; file_sha256
gives the hash of a config file, so a result can name the exact settings used.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodeVersion:
    """Git state of the repository when something was produced.

    Attributes:
        commit: HEAD commit hash, or "unknown" if git is unavailable.
        dirty: True if tracked files had uncommitted changes (untracked files
            are ignored). True as well when the state is unknown.
    """

    commit: str
    dirty: bool


def code_version(repo_root: Path) -> CodeVersion:
    """Read the HEAD commit and dirty flag of the repository at `repo_root`."""
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain",
             "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return CodeVersion(commit="unknown", dirty=True)
    if head.returncode != 0 or status.returncode != 0:
        return CodeVersion(commit="unknown", dirty=True)
    return CodeVersion(commit=head.stdout.strip(), dirty=bool(status.stdout.strip()))


def file_sha256(path: Path) -> str:
    """SHA-256 of a file's bytes, as lowercase hex."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_hashes(paths: dict[str, Path]) -> dict[str, str]:
    """SHA-256 of each named config file, keyed by the given names."""
    return {name: file_sha256(path) for name, path in sorted(paths.items())}
