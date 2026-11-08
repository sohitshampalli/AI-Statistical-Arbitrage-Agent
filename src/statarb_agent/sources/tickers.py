"""Ticker validation. Runs before a ticker is used in any file path or request.

Steps, in this order:
1. Reject any non-ASCII character. This runs before uppercasing because
   str.upper maps some non-ASCII letters to ASCII ones (dotless i becomes I,
   long s becomes S), which would let a look-alike through.
2. Uppercase, so "ko" and "brk.b" are accepted.
3. Require ASCII letters and digits, with "." or "-" only between two
   alphanumeric runs (so "..", ".KO" and "KO-" are rejected).
4. Normalise share class separators to Yahoo's "-" form: BRK.B becomes BRK-B.

Anything else is rejected, not repaired: whitespace, slashes, index symbols
such as ^GSPC.
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
        The ticker uppercased, with "." replaced by "-".

    Raises:
        TypeError: If `raw` is not a str.
        ValueError: If `raw` contains a non-ASCII character or anything else
            outside the allowed set, has a leading, trailing or doubled
            separator, or is longer than MAX_TICKER_LENGTH characters.
    """
    if not isinstance(raw, str):
        raise TypeError(f"ticker must be a str, got {type(raw).__name__}")
    if not raw.isascii():
        raise ValueError(f"invalid ticker {raw!r}: only ASCII characters are allowed")
    upper = raw.upper()
    if not (0 < len(upper) <= MAX_TICKER_LENGTH) or not _TICKER.fullmatch(upper):
        raise ValueError(
            f"invalid ticker {raw!r}: use 1 to {MAX_TICKER_LENGTH} letters or digits, "
            "optionally joined by single '.' or '-' (for example KO, BRK.B)"
        )
    return upper.replace(".", "-")
