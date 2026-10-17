"""Placebo, lag-decay, and timing checks for BTCUSDT OFI research.

Checks:
- Continuous, unique, one-second feature-availability timestamps.
- Correct 5-second decision grid and 1-second entry / 5-second holding logic.
- Lagged-OFI performance decay when only past OFI is used.
- Within-day shuffled-OFI placebo, preserving each day's OFI distribution and
  therefore approximately preserving each day's threshold signal count.
- Random signals matched to the observed trade count and long/short counts
  for each day.

"""

from __future__ import annotations

from pathlib import Path
import time

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "BTCUSDT-targets-2025-06-01_to_2025-06-07.csv"
)
REPORT_DIR = PROJECT_DIR / "reports"

SIGNAL_INTERVAL_SECONDS = 5
ENTRY_DELAY_SECONDS = 1
HOLD_SECONDS = 5
LONG_THRESHOLD = 0.75
SHORT_THRESHOLD = -0.75
LAGS_TO_TEST = (0, 1, 2, 5, 10, 30)
N_PERMUTATIONS = 500
RANDOM_SEED = 20251017


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Development dataset not found: {DATA_PATH}\n"
            "Expected BTCUSDT-targets-2025-06-01_to_2025-06-07.csv."
        )

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")

    required = {"flow_imbalance", "close_price", "trade_count", "total_qty_btc"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Feature availability timestamps must be a DatetimeIndex.")
    if df.index.tz is None:
        raise ValueError("Timestamps must be timezone-aware (UTC).")
    if df.index.has_duplicates:
        raise ValueError("Duplicate timestamps found.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("Timestamps are not chronologically sorted.")
    if not ((df.index.microsecond == 0) & (df.index.nanosecond == 0)).all():
        raise ValueError("Timestamps are not aligned to exact seconds.")

    diffs = df.index.to_series().diff().dropna()
    if not (diffs == pd.Timedelta(seconds=1)).all():
        raise ValueError("Dataset is not a continuous one-second grid.")

    # Expected feature-availability index after shifting the 7 daily bars
    # forward by one second: 00:00:01 on June 1 through 00:00:00 on June 8.
    expected_index = pd.date_range(
        start="2025-06-01 00:00:01", periods=7 * 86_400, freq="s", tz="UTC"
    )
    if not df.index.equals(expected_index):
        raise ValueError(
            "Timestamp range does not match the expected June 1-7 development grid. "
            f"Got {df.index[0]} through {df.index[-1]} with {len(df):,} rows."
        )

    return df


def direction_from_ofi(ofi: np.ndarray) -> np.ndarray:
    """Frozen threshold rule: +1 long, -1 short, 0 flat."""
    out = np.zeros(len(ofi), dtype=np.int8)
    out[np.isfinite(ofi) & (ofi >= LONG_THRESHOLD)] = 1
    out[np.isfinite(ofi) & (ofi <= SHORT_THRESHOLD)] = -1
    return out


def make_decision_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Create the fixed decision grid and proxy returns for the frozen rule."""
    mark = pd.to_numeric(df["close_price"], errors="coerce").ffill()
    entry = mark.shift(-ENTRY_DELAY_SECONDS)
    exit_price = mark.shift(-(ENTRY_DELAY_SECONDS + HOLD_SECONDS))

    # Use the second field rather than raw timestamp integer units. This
    # should give 00, 05, 10, ..., 55 each minute on the full UTC grid.
    decision_mask = df.index.second % SIGNAL_INTERVAL_SECONDS == 0
    decisions = pd.DataFrame(index=df.index[decision_mask])
    decisions["ofi"] = pd.to_numeric(df["flow_imbalance"], errors="coerce").loc[
        decisions.index
    ]
    decisions["entry_price"] = entry.loc[decisions.index]
    decisions["exit_price"] = exit_price.loc[decisions.index]
    decisions["underlying_return_bps"] = (
        decisions["exit_price"] / decisions["entry_price"] - 1.0
    ) * 10_000
    decisions["valid_prices"] = (
        decisions["entry_price"].notna()
        & decisions["exit_price"].notna()
        & (decisions["entry_price"] > 0)
        & (decisions["exit_price"] > 0)
    )
    decisions["date"] = decisions.index.strftime("%Y-%m-%d")
    decisions["observed_direction"] = direction_from_ofi(
        decisions["ofi"].to_numpy(dtype=float)
    )
    return decisions


def assert_timing_logic(df: pd.DataFrame, decisions: pd.DataFrame) -> list[str]:
    """Run assertions on real timestamps and a synthetic price sequence."""
    checks: list[str] = []

    assert len(df) == 7 * 86_400, "Expected exactly 604,800 one-second rows."
    checks.append("PASS: 604,800 expected one-second rows are present.")
    assert df.index.is_unique and df.index.is_monotonic_increasing
    assert (df.index.to_series().diff().dropna() == pd.Timedelta(seconds=1)).all()
    checks.append("PASS: timestamps are unique, sorted, UTC-aware and one second apart.")

    expected_decisions = len(df) // SIGNAL_INTERVAL_SECONDS
    assert len(decisions) == expected_decisions == 120_960, (
        f"Expected 120,960 decisions, got {len(decisions):,}."
    )
    assert (decisions.index.second % SIGNAL_INTERVAL_SECONDS == 0).all()
    checks.append("PASS: the five-second decision grid contains exactly 120,960 rows.")

    # Synthetic test: at decision time t, entry is t+1, exit is t+6;
    # elapsed holding time between entry and exit is exactly 5 seconds.
    toy_index = pd.date_range("2025-06-01 00:00:01", periods=8, freq="s", tz="UTC")
    toy_price = pd.Series(np.arange(100.0, 108.0), index=toy_index)
    toy_entry = toy_price.shift(-ENTRY_DELAY_SECONDS)
    toy_exit = toy_price.shift(-(ENTRY_DELAY_SECONDS + HOLD_SECONDS))
    t0 = toy_index[0]
    assert toy_entry.loc[t0] == 101.0
    assert toy_exit.loc[t0] == 106.0
    assert (toy_index[ENTRY_DELAY_SECONDS] - t0) == pd.Timedelta(seconds=1)
    assert (
        toy_index[ENTRY_DELAY_SECONDS + HOLD_SECONDS] - toy_index[ENTRY_DELAY_SECONDS]
    ) == pd.Timedelta(seconds=HOLD_SECONDS)
    checks.append("PASS: synthetic timing test confirms entry at t+1s and exit at t+6s.")

    # The two price shifts are strictly forward from the signal timestamp.
    assert ENTRY_DELAY_SECONDS > 0 and HOLD_SECONDS > 0
    checks.append("PASS: entry and exit price proxies are shifted forward, not backward.")

    return checks


def mean_and_rate(returns: np.ndarray) -> tuple[float, float, float]:
    if len(returns) == 0:
        return np.nan, np.nan, np.nan
    return (
        float(np.mean(returns)),
        float(np.median(returns)),
        float(np.mean(returns > 0) * 100.0),
    )


def run_lag_decay(decisions: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Compare signals made from current and older OFI observations."""
    mark = pd.to_numeric(df["close_price"], errors="coerce").ffill()
    entry = mark.shift(-ENTRY_DELAY_SECONDS)
    exit_price = mark.shift(-(ENTRY_DELAY_SECONDS + HOLD_SECONDS))
    underlying_full = (exit_price / entry - 1.0) * 10_000
    decision_mask = df.index.second % SIGNAL_INTERVAL_SECONDS == 0
    valid = (
        entry.loc[decision_mask].notna().to_numpy()
        & exit_price.loc[decision_mask].notna().to_numpy()
        & (entry.loc[decision_mask].to_numpy() > 0)
        & (exit_price.loc[decision_mask].to_numpy() > 0)
    )
    underlying = underlying_full.loc[decision_mask].to_numpy(dtype=float)
    base_index = df.index[decision_mask]

    rows = []
    for lag_seconds in LAGS_TO_TEST:
        lagged_ofi = pd.to_numeric(df["flow_imbalance"], errors="coerce").shift(
            lag_seconds
        ).loc[base_index].to_numpy(dtype=float)
        direction = direction_from_ofi(lagged_ofi)
        selected = (direction != 0) & valid & np.isfinite(underlying)
        gross = direction[selected] * underlying[selected]
        mean_bps, median_bps, win_pct = mean_and_rate(gross)
        rows.append(
            {
                "ofi_lag_seconds": lag_seconds,
                "decision_timestamps": len(base_index),
                "valid_trades": len(gross),
                "signal_rate_pct": 100.0 * float(selected.sum()) / len(base_index),
                "mean_gross_return_bps": mean_bps,
                "median_gross_return_bps": median_bps,
                "gross_win_rate_pct": win_pct,
            }
        )
    return pd.DataFrame(rows)


def run_placebos(decisions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run shuffled-OFI and frequency/side-matched random-signal placebos."""
    rng = np.random.default_rng(RANDOM_SEED)

    ofi = decisions["ofi"].to_numpy(dtype=float)
    underlying = decisions["underlying_return_bps"].to_numpy(dtype=float)
    valid_prices = decisions["valid_prices"].to_numpy(dtype=bool)
    day_values = decisions["date"].to_numpy()
    observed_direction = decisions["observed_direction"].to_numpy(dtype=np.int8)
    observed_mask = (observed_direction != 0) & valid_prices & np.isfinite(underlying)
    observed_returns = observed_direction[observed_mask] * underlying[observed_mask]
    observed_mean = float(np.mean(observed_returns))

    unique_days = np.unique(day_values)
    day_masks = [day_values == day for day in unique_days]
    shuffled_means = np.empty(N_PERMUTATIONS, dtype=float)
    random_means = np.empty(N_PERMUTATIONS, dtype=float)

    # Day-level trade counts and side counts for the matched random baseline.
    daily_specs = []
    for day, day_mask in zip(unique_days, day_masks):
        eligible = np.flatnonzero(day_mask & valid_prices & np.isfinite(underlying))
        orig_day_direction = observed_direction[eligible]
        n_long = int(np.sum(orig_day_direction == 1))
        n_short = int(np.sum(orig_day_direction == -1))
        daily_specs.append((eligible, n_long, n_short))

    for rep in range(N_PERMUTATIONS):
        # Placebo 1: shuffle OFI values within each day. The day's value
        # distribution (including NaNs) is preserved; temporal alignment is not.
        shuffled_ofi = ofi.copy()
        for day_mask in day_masks:
            shuffled_ofi[day_mask] = rng.permutation(shuffled_ofi[day_mask])
        shuffled_direction = direction_from_ofi(shuffled_ofi)
        m = (shuffled_direction != 0) & valid_prices & np.isfinite(underlying)
        if m.any():
            shuffled_means[rep] = float(np.mean(shuffled_direction[m] * underlying[m]))
        else:
            shuffled_means[rep] = np.nan

        # Placebo 2: choose the same number of trades on each day, and keep
        # that day's long/short counts, but randomly assign decision times.
        random_returns_parts = []
        for eligible, n_long, n_short in daily_specs:
            n_trades = n_long + n_short
            if n_trades == 0:
                continue
            chosen = rng.choice(eligible, size=n_trades, replace=False)
            random_direction = np.concatenate(
                [np.ones(n_long, dtype=np.int8), -np.ones(n_short, dtype=np.int8)]
            )
            rng.shuffle(random_direction)
            random_returns_parts.append(random_direction * underlying[chosen])
        random_returns = np.concatenate(random_returns_parts) if random_returns_parts else np.array([])
        random_means[rep] = float(np.mean(random_returns)) if len(random_returns) else np.nan

    def summarize_null(name: str, values: np.ndarray) -> dict:
        values = values[np.isfinite(values)]
        # One-sided empirical test: placebo mean >= observed mean.
        p_upper = (1 + int(np.sum(values >= observed_mean))) / (len(values) + 1)
        return {
            "placebo": name,
            "observed_mean_gross_bps": observed_mean,
            "placebo_repetitions": len(values),
            "placebo_mean_bps": float(np.mean(values)),
            "placebo_std_bps": float(np.std(values, ddof=1)),
            "placebo_p05_bps": float(np.quantile(values, 0.05)),
            "placebo_p50_bps": float(np.quantile(values, 0.50)),
            "placebo_p95_bps": float(np.quantile(values, 0.95)),
            "empirical_upper_tail_p": float(p_upper),
            "observed_exceeds_95pct_placebo": bool(observed_mean > np.quantile(values, 0.95)),
        }

    placebo_results = pd.DataFrame(
        [
            summarize_null("OFI shuffled within day", shuffled_means),
            summarize_null("Random times, matched daily trade and side counts", random_means),
        ]
    )

    # Also save individual null values so the report plot can be recreated.
    null_distribution = pd.DataFrame(
        {
            "replicate": np.arange(1, N_PERMUTATIONS + 1),
            "within_day_shuffled_ofi_mean_bps": shuffled_means,
            "matched_random_signal_mean_bps": random_means,
        }
    )
    return placebo_results, null_distribution


def main() -> None:
    start = time.time()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data()
    decisions = make_decision_frame(df)
    timing_checks = assert_timing_logic(df, decisions)

    observed_direction = decisions["observed_direction"].to_numpy(dtype=np.int8)
    valid = decisions["valid_prices"].to_numpy(dtype=bool)
    underlying = decisions["underlying_return_bps"].to_numpy(dtype=float)
    selected = (observed_direction != 0) & valid & np.isfinite(underlying)
    observed_gross = observed_direction[selected] * underlying[selected]

    print("=" * 82)
    print("PLACEBO, LAG-DECAY AND TIMING CHECKS — JUNE 1-7 DEVELOPMENT DATA")
    print("=" * 82)
    print(f"Loaded {len(df):,} one-second rows; {len(decisions):,} five-second decision timestamps.")
    print(f"Frozen threshold signals before price checks: {int((observed_direction != 0).sum()):,}")
    print(f"Valid frozen-rule trades: {len(observed_gross):,}")
    print(f"Observed frozen-rule mean gross return: {np.mean(observed_gross):.6f} bps/trade")

    print("\nTIMING / DATA ASSERTIONS")
    for check in timing_checks:
        print(check)

    print("\nLAG-DECAY TEST")
    lag_results = run_lag_decay(decisions, df)
    print(lag_results.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(
        "Interpretation: each row uses OFI observed that many seconds before the same decision time; "
        "returns are measured from the delayed entry proxy to the fixed exit proxy."
    )

    print(f"\nPLACEBO TESTS ({N_PERMUTATIONS} repetitions each)")
    placebo_results, null_distribution = run_placebos(decisions)
    print(placebo_results.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(
        "Interpretation: the within-day shuffle preserves each day's OFI distribution but breaks its "
        "timing; the random baseline matches each day's number of long and short trades. "
        "Neither placebo models real execution costs."
    )

    lag_path = REPORT_DIR / "placebo_lag_decay_june_2025.csv"
    placebo_path = REPORT_DIR / "placebo_summary_june_2025.csv"
    null_path = REPORT_DIR / "placebo_null_distributions_june_2025.csv"
    checks_path = REPORT_DIR / "timing_checks_june_2025.txt"

    lag_results.to_csv(lag_path, index=False)
    placebo_results.to_csv(placebo_path, index=False)
    null_distribution.to_csv(null_path, index=False)
    checks_path.write_text("\n".join(timing_checks) + "\n", encoding="utf-8")

    print("\nSaved outputs:")
    print(f"  {lag_path}")
    print(f"  {placebo_path}")
    print(f"  {null_path}")
    print(f"  {checks_path}")
    print(f"Completed in {time.time() - start:.1f}s")
    print("\nNo data outside June 1-7, 2025 was read or changed.")


if __name__ == "__main__":
    main()
