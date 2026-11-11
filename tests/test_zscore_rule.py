"""Tests for the z-score rule. Every expected sequence is worked out by hand."""

from __future__ import annotations

import numpy as np
import pytest

from statarb_agent.signals.zscore import REASONS, SignalParams, decide_positions

PARAMS = SignalParams(entry_z=2.0, exit_z=0.5, stop_z=4.0, time_stop_bars=5)
NAN = float("nan")


def run(
    z: list[float],
    *,
    tradeable: list[bool] | None = None,
    window_last: list[int] | None = None,
    params: SignalParams = PARAMS,
) -> tuple[list[int], list[str]]:
    n = len(z)
    last = np.zeros(n, dtype=bool)
    for i in window_last or []:
        last[i] = True
    trade = np.ones(n, dtype=bool) if tradeable is None else np.array(tradeable)
    out = decide_positions(np.array(z), trade, last, params)
    assert set(out.reason) <= set(REASONS)
    return [int(v) for v in out.target], list(out.reason)


def test_long_entry_and_exit() -> None:
    target, reason = run([0.0, -1.9, -2.1, -1.0, -0.6, -0.4, 0.0])
    assert target == [0, 0, 1, 1, 1, 0, 0]
    assert reason == ["", "", "entry_long", "", "", "exit", ""]


def test_short_entry_and_exit() -> None:
    target, reason = run([0.0, 2.5, 1.0, 0.49, 0.3])
    assert target == [0, -1, -1, 0, 0]
    assert reason == ["", "entry_short", "", "exit", ""]


def test_thresholds_are_strict() -> None:
    # exactly at entry: no trade; just beyond: trade
    assert run([2.0, -2.0])[0] == [0, 0]
    assert run([2.0000001])[0] == [-1]
    # exactly at exit: stay; exactly at stop: stay (and entry at the stop is allowed)
    assert run([-3.0, -0.5, -4.0, -0.49])[0] == [1, 1, 1, 0]
    assert run([4.0])[1] == ["entry_short"]
    assert run([4.0000001])[0] == [0]


def test_exit_when_z_crosses_to_the_other_side_without_reversing() -> None:
    target, reason = run([-2.5, 3.0, 3.0])
    # bar 1: long exits because z is far above -0.5; no short entry on the same bar
    assert target == [1, 0, -1]
    assert reason == ["entry_long", "exit", "entry_short"]


def test_stop_blocks_reentry_until_the_spread_comes_back() -> None:
    z = [-2.5, -4.5, -3.0, -2.5, -0.6, -0.4, -2.2, -1.0]
    target, reason = run(z)
    assert target == [1, 0, 0, 0, 0, 0, 1, 1]
    assert reason == ["entry_long", "stop", "", "", "", "", "entry_long", ""]


def test_block_is_lifted_only_inside_the_exit_band() -> None:
    # after the stop z moves to the other side without passing through |z| < 0.5
    target, _ = run([2.5, 4.5, -3.0, 3.0, 0.2, 2.5])
    assert target == [-1, 0, 0, 0, 0, -1]


def test_time_stop_counts_bars_since_the_entry_decision() -> None:
    # entry decided at bar 1; bars 2..5 are in-trade bars 1..4; bar 6 is the 5th
    z = [0.0, -2.5, -2.4, -2.3, -2.2, -2.1, -2.0, -2.6, -0.1, -2.6]
    target, reason = run(z)
    assert target == [0, 1, 1, 1, 1, 1, 0, 0, 0, 1]
    assert reason[6] == "time_stop"
    assert reason[7] == ""  # blocked: z = -2.6 would otherwise enter
    assert reason[9] == "entry_long"  # bar 8 was inside the exit band


def test_exit_and_stop_take_priority_over_the_time_stop() -> None:
    params = SignalParams(entry_z=2.0, exit_z=0.5, stop_z=4.0, time_stop_bars=2)
    assert run([-2.5, -2.4, -0.1], params=params)[1] == ["entry_long", "", "exit"]
    assert run([-2.5, -2.4, -4.5], params=params)[1] == ["entry_long", "", "stop"]
    assert run([-2.5, -2.4, -2.3], params=params)[1] == ["entry_long", "", "time_stop"]
    one = SignalParams(entry_z=2.0, exit_z=0.5, stop_z=4.0, time_stop_bars=1)
    assert run([-2.5, -2.4], params=one)[1] == ["entry_long", "time_stop"]


def test_window_end_forces_flat_and_clears_the_block() -> None:
    z = [-2.5, -4.5, -3.0, -3.0, -2.5]
    target, reason = run(z, window_last=[2])
    # stopped at bar 1 (blocked), bar 2 ends the window, bar 3 may enter again
    assert target == [1, 0, 0, 1, 1]
    assert reason == ["entry_long", "stop", "", "entry_long", ""]
    target, reason = run([-2.5, -2.4, -2.3, -2.2], window_last=[2])
    assert target == [1, 1, 0, 1]
    assert reason == ["entry_long", "", "window_end", "entry_long"]
    # no entry on the last bar of a window
    assert run([0.0, -2.5], window_last=[1])[0] == [0, 0]


def test_untradeable_or_nan_bars_force_flat_and_never_enter() -> None:
    target, reason = run([-2.5, -2.4, -2.3, -2.2], tradeable=[True, True, False, True])
    assert target == [1, 1, 0, 1]
    assert reason == ["entry_long", "", "not_tradeable", "entry_long"]
    target, reason = run([-2.5, NAN, -2.5, NAN])
    assert target == [1, 0, 1, 0]
    assert reason == ["entry_long", "not_tradeable", "entry_long", "not_tradeable"]
    assert run([NAN, -2.5], tradeable=[True, False]) == ([0, 0], ["", ""])
    assert run([float("inf"), float("-inf")])[0] == [0, 0]


def test_decisions_depend_only_on_earlier_bars() -> None:
    """Look-ahead test: cutting the series after any bar leaves the past unchanged,
    and changing later bars leaves earlier decisions unchanged."""
    rng = np.random.default_rng(0)
    n = 400
    z = np.cumsum(rng.standard_normal(n)) * 0.6
    z[rng.integers(0, n, 10)] = np.nan
    tradeable = rng.random(n) > 0.05
    window_last = np.zeros(n, dtype=bool)
    window_last[62::63] = True
    full = decide_positions(z, tradeable, window_last, PARAMS)
    assert set(full.target) == {-1, 0, 1}  # the test data exercises both sides
    for cut in (1, 2, 63, 64, 150, 399):
        part = decide_positions(z[:cut], tradeable[:cut], window_last[:cut], PARAMS)
        np.testing.assert_array_equal(part.target, full.target[:cut])
        np.testing.assert_array_equal(part.reason, full.reason[:cut])
    changed = z.copy()
    changed[200:] = rng.standard_normal(n - 200) * 5.0
    other = decide_positions(changed, tradeable, window_last, PARAMS)
    np.testing.assert_array_equal(other.target[:200], full.target[:200])
    assert not np.array_equal(other.target[200:], full.target[200:])


def test_position_changes_always_have_a_reason() -> None:
    rng = np.random.default_rng(1)
    z = np.cumsum(rng.standard_normal(2000)) * 0.5
    out = decide_positions(z, np.ones(2000, bool), np.zeros(2000, bool), PARAMS)
    previous = np.r_[0, out.target[:-1]]
    changed = out.target != previous
    assert ((out.reason != "") == changed).all()
    # never a direct flip between long and short
    assert not ((previous * out.target) == -1).any()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"entry_z": 2.0, "exit_z": 2.0, "stop_z": 4.0, "time_stop_bars": 5},
        {"entry_z": 2.0, "exit_z": 0.5, "stop_z": 2.0, "time_stop_bars": 5},
        {"entry_z": 2.0, "exit_z": -0.1, "stop_z": 4.0, "time_stop_bars": 5},
        {"entry_z": 2.0, "exit_z": 0.5, "stop_z": 4.0, "time_stop_bars": 0},
        {"entry_z": 2.0, "exit_z": 0.5, "stop_z": float("inf"), "time_stop_bars": 5},
    ],
)
def test_invalid_params_raise(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        SignalParams(**kwargs)


def test_wrong_types_and_shapes_raise() -> None:
    with pytest.raises(TypeError):
        SignalParams(entry_z=2.0, exit_z=0.5, stop_z=4.0, time_stop_bars=5.0)
    with pytest.raises(TypeError):
        SignalParams(entry_z="2", exit_z=0.5, stop_z=4.0, time_stop_bars=5)
    with pytest.raises(ValueError, match="equally long"):
        decide_positions(np.zeros(3), np.ones(2, bool), np.zeros(3, bool), PARAMS)
