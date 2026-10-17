import argparse
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_START_DATE = "2026-09-01"
DEFAULT_END_DATE = "2026-09-30"


def trades_path_for(start_date, end_date):
    return (
        PROJECT_DIR
        / "reports"
        / f"backtest_trades_{start_date}_to_{end_date}.csv"
    )

BOOTSTRAP_REPS = 20_000
BLOCK_LENGTHS = (1, 3, 5)
SEED = 42


def block_bootstrap_ci(values, block_length, rng):
    """
    Moving-block bootstrap of daily mean returns.

    Blocks preserve short runs of adjacent days. This helps avoid
    treating all trades within a day as independent observations.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)

    if n < block_length:
        return np.nan, np.nan

    bootstrap_means = np.empty(BOOTSTRAP_REPS)

    for b in range(BOOTSTRAP_REPS):
        sampled = []

        while len(sampled) < n:
            start = rng.integers(0, n)
            block = [
                values[(start + offset) % n]
                for offset in range(block_length)
            ]
            sampled.extend(block)

        bootstrap_means[b] = np.mean(sampled[:n])

    low, high = np.quantile(bootstrap_means, [0.025, 0.975])
    return float(low), float(high)


def main():
    parser = argparse.ArgumentParser(
        description="Summarise backtest trades and bootstrap daily means."
    )
    parser.add_argument(
        "--start-date",
        default=DEFAULT_START_DATE,
        help="First date in YYYY-MM-DD format (default: %(default)s)",
    )
    parser.add_argument(
        "--end-date",
        default=DEFAULT_END_DATE,
        help="Last date in YYYY-MM-DD format (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        start_date = pd.Timestamp(args.start_date).date().isoformat()
        end_date = pd.Timestamp(args.end_date).date().isoformat()
    except (TypeError, ValueError):
        parser.error("Dates must be valid dates in YYYY-MM-DD format")

    if start_date != args.start_date or end_date != args.end_date:
        parser.error("Dates must use YYYY-MM-DD format")

    if end_date < start_date:
        parser.error("--end-date must be on or after --start-date")

    trades_path = trades_path_for(start_date, end_date)

    if not trades_path.exists():
        raise FileNotFoundError(
            f"Trade file not found: {trades_path}\\n"
            "Run src/backtest.py for the same date range first."
        )

    trades = pd.read_csv(trades_path)

    required = {"date", "side", "gross_return_bps"}
    missing = required - set(trades.columns)

    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    trades["gross_return_bps"] = pd.to_numeric(
        trades["gross_return_bps"], errors="coerce"
    )
    trades = trades.dropna(
        subset=["date", "side", "gross_return_bps"]
    )

    if trades.empty:
        raise ValueError("No valid trades found.")

    daily = trades.groupby("date")["gross_return_bps"].agg(
        ["mean", "median", "count"]
    )

    overall_mean = trades["gross_return_bps"].mean()
    overall_win_rate = (
        trades["gross_return_bps"] > 0
    ).mean()

    print("=" * 72)
    print(f"FINAL EVALUATION — {start_date} to {end_date}")
    print("=" * 72)
    print(f"Trades: {len(trades):,}")
    print(f"Days: {len(daily)}")
    print(f"Trade-weighted mean gross return: {overall_mean:.6f} bps")
    print(f"Gross win rate: {overall_win_rate:.2%}")
    print(
        "Days with positive mean gross return: "
        f"{int((daily['mean'] > 0).sum())}/{len(daily)}"
    )
    print(f"Lowest daily mean: {daily['mean'].min():.6f} bps")
    print(f"Highest daily mean: {daily['mean'].max():.6f} bps")
    print(
        "Unweighted mean of daily means: "
        f"{daily['mean'].mean():.6f} bps"
    )

    print("\n" + "-" * 72)
    print("LONG VERSUS SHORT")
    print("-" * 72)

    side_summary = trades.groupby("side")["gross_return_bps"].agg(
        trades="size",
        mean_bps="mean",
        median_bps="median",
        win_rate=lambda x: (x > 0).mean(),
    )
    print(side_summary.to_string(
        float_format=lambda x: f"{x:.5f}"
    ))

    print("\n" + "-" * 72)
    print("UNCERTAINTY: BOOTSTRAP OF DAILY MEAN RETURNS")
    print("-" * 72)
    print(
        "These intervals use days, not individual trades, as the "
        "resampling units. They are descriptive uncertainty estimates."
    )

    rng = np.random.default_rng(SEED)

    for block_length in BLOCK_LENGTHS:
        low, high = block_bootstrap_ci(
            daily["mean"].values,
            block_length,
            rng,
        )
        print(
            f"Block length {block_length} day(s): "
            f"95% interval [{low:.6f}, {high:.6f}] bps"
        )

    print("\n" + "-" * 72)
    print("COST SENSITIVITY")
    print("-" * 72)
    print("Cost (bps) | Mean net return (bps)")

    costs = sorted(set([
        0.0,
        0.025,
        0.05,
        0.075,
        float(overall_mean),
        0.1,
        0.2,
        1.0,
    ]))

    for cost in costs:
        print(
            f"{cost:>10.5f} | "
            f"{overall_mean - cost:>21.5f}"
        )

    print("\nNote: costs are hypothetical round-trip costs.")
    print("They exclude the additional uncertainty of actual execution.")


if __name__ == "__main__":
    main()
