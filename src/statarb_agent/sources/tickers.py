"""Ticker validation. Runs before a ticker is used in any file path or request.

Allowed: uppercase ASCII letters, digits, "." and "-", with a separator only
between two alphanumeric runs (so "..", ".KO" and "KO-" are rejected). Share
class separators are normalised to Yahoo's "-" form: BRK.B becomes BRK-B.
Anything else is rejected, not repaired: lowercase, whitespace, slashes,
index symbols such as ^GSPC, and non-ASCII look-alikes.
"""

from __future__ import annotations

import re
from typing import Final

MAX_TICKER_LENGTH: Final = 12
_TICKER: Final = re.compile(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*")


def normalise_ticker(raw: str) -> str:
    """Validate a ticker and return it in Yahoo's form.

    Args:
        raw: Ticker as typed, for example "KO" or "BRK.B".

    Returns:
        The ticker with "." replaced by "-".

    Raises:
        TypeError: If `raw` is not a str.
        ValueError: If `raw` contains anything outside the allowed set, has a
            leading, trailing or doubled separator, or is longer than
            MAX_TICKER_LENGTH characters.
    """
    if not isinstance(raw, str):
        raise TypeError(f"ticker must be a str, got {type(raw).__name__}")
    if not (0 < len(raw) <= MAX_TICKER_LENGTH) or not _TICKER.fullmatch(raw):
        raise ValueError(
            f"invalid ticker {raw!r}: use 1 to {MAX_TICKER_LENGTH} uppercase letters "
            "or digits, optionally joined by single '.' or '-' (for example KO, BRK.B)"
        )
    return raw.replace(".", "-")
