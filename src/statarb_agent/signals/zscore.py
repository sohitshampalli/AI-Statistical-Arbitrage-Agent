"""The z-score trading rule as a state machine over bars.

Input: one z-score per bar. z measures how far the spread is from its mean in
standard deviations, with mean and deviation estimated only from earlier data
(the backtest engine does that). A low z means the spread is cheap.

Position after each bar's decision:
    +1  long the spread  (entered when z was below -entry_z)
    -1  short the spread (entered when z was above +entry_z)
     0  flat

Rule at each bar, in this order:

1. Last signal bar of a trading window: go flat ("window_end"). The stop block
   (below) is cleared, because the next window has new parameters.
2. Bar not tradeable (no parameters, or z is not finite): go flat
   ("not_tradeable"); no entry.
3. In a position. Let d = -z for a long spread and d = +z for a short one, the
   distance on the side the trade was entered.
   a. d > stop_z: exit ("stop") and block new entries.
   b. d < exit_z: exit ("exit"). This includes z having crossed zero.
   c. the trade has lasted time_stop_bars bars since its entry decision: exit
      ("time_stop") and block new entries.
4. Flat. If entries are blocked, the block is lifted once |z| < exit_z, that is
   once the spread has come back. Otherwise enter long if
   entry_z < -z <= stop_z ("entry_long") or short if entry_z < z <= stop_z
   ("entry_short"). No entry beyond the stop level.

A position is never reversed in one bar: an exit bar ends flat.

The comparisons are strict as in the brief: enter when |z| > entry, exit when
|z| < exit, stop when |z| > stop.

The decision at bar t uses z up to bar t only. It is acted on at the next bar
by the backtest engine, never on bar t itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FLAT = 0
LONG_SPREAD = 1
SHORT_SPREAD = -1
REASONS = (
    "", "entry_long", "entry_short", "exit", "stop", "time_stop", "window_end",
    "not_tradeable",
)


@dataclass(frozen=True)
class SignalParams:
    """Thresholds of the rule, in z units, and the time stop in bars.

    Attributes:
        entry_z: Enter when |z| is above this.
        exit_z: Exit when the distance on the entry side is below this.
        stop_z: Stop out when the distance on the entry side is above this.
        time_stop_bars: Exit a trade this many bars after its entry decision.
    """

    entry_z: float
    exit_z: float
    stop_z: float
    time_stop_bars: int

    def __post_init__(self) -> None:
        for name in ("entry_z", "exit_z", "stop_z"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number, got {value!r}")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if not 0.0 <= self.exit_z < self.entry_z < self.stop_z:
            raise ValueError("need 0 <= exit_z < entry_z < stop_z")
        if isinstance(self.time_stop_bars, bool) or not isinstance(
            self.time_stop_bars, int
        ):
            raise TypeError("time_stop_bars must be an integer")
        if self.time_stop_bars < 1:
            raise ValueError("time_stop_bars must be at least 1")


@dataclass(frozen=True)
class Decisions:
    """Output of decide_positions, one entry per bar.

    Attributes:
        target: Position (+1, 0, -1) wanted after the bar's decision.
        reason: Why the position changed at this bar, or "" if it did not.
    """

    target: np.ndarray
    reason: np.ndarray


def decide_positions(
    z: np.ndarray,
    tradeable: np.ndarray,
    window_last: np.ndarray,
    params: SignalParams,
) -> Decisions:
    """Apply the rule in the module docstring to a sequence of bars.

    Args:
        z: z-score per bar. NaN is allowed and makes the bar not tradeable.
        tradeable: True where the bar may hold or open a position.
        window_last: True on the last signal bar of each trading window.
        params: Thresholds.

    Returns:
        Decisions. target[t] and reason[t] depend on bars 0..t only, so cutting
        the inputs after any bar leaves the earlier outputs unchanged.

    Raises:
        ValueError: If the three inputs are not one-dimensional and equally long.
    """
    z = np.asarray(z, dtype=float)
    tradeable = np.asarray(tradeable, dtype=bool)
    window_last = np.asarray(window_last, dtype=bool)
    if z.ndim != 1 or tradeable.shape != z.shape or window_last.shape != z.shape:
        raise ValueError("z, tradeable and window_last must be 1-D and equally long")
    n = len(z)
    target = np.zeros(n, dtype=np.int8)
    reason = np.full(n, "", dtype=object)
    position = FLAT
    bars_in_trade = 0
    blocked = False
    for t in range(n):
        value = z[t]
        if window_last[t]:
            if position != FLAT:
                reason[t] = "window_end"
            position = FLAT
            blocked = False
        elif not tradeable[t] or not math.isfinite(value):
            if position != FLAT:
                reason[t] = "not_tradeable"
            position = FLAT
        elif position != FLAT:
            bars_in_trade += 1
            distance = -value if position == LONG_SPREAD else value
            if distance > params.stop_z:
                reason[t] = "stop"
                position = FLAT
                blocked = True
            elif distance < params.exit_z:
                reason[t] = "exit"
                position = FLAT
            elif bars_in_trade >= params.time_stop_bars:
                reason[t] = "time_stop"
                position = FLAT
                blocked = True
        else:
            if blocked and abs(value) < params.exit_z:
                blocked = False
            if not blocked:
                if params.entry_z < -value <= params.stop_z:
                    position = LONG_SPREAD
                    reason[t] = "entry_long"
                    bars_in_trade = 0
                elif params.entry_z < value <= params.stop_z:
                    position = SHORT_SPREAD
                    reason[t] = "entry_short"
                    bars_in_trade = 0
        target[t] = position
    return Decisions(target=target, reason=reason)
