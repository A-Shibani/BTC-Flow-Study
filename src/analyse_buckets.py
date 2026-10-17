from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "BTCUSDT-targets-2025-06-01_to_2025-06-07.csv"
)

HORIZONS = (1, 5, 30)

# Fixed boundaries make comparisons between horizons easier.
BINS = [
    -1.000001, -0.75, -0.50, -0.25,
    0.0, 0.25, 0.50, 0.75, 1.000001,
]


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    feature = "flow_imbalance"

    print("=" * 78)
    print("CONDITIONAL RETURNS BY ORDER-FLOW IMBALANCE")
    print("=" * 78)
    print("Positive returns are price increases; negative returns are declines.")
    print("Returns are measured in basis points (bps).")
    print("These are descriptive statistics, not a trading backtest.")

    for horizon in HORIZONS:
        target = f"future_return_{horizon}s_bps"

        valid = df[[feature, target]].replace(
            [np.inf, -np.inf], np.nan
        ).dropna().copy()

        valid["imbalance_bucket"] = pd.cut(
            valid[feature],
            bins=BINS,
            include_lowest=True,
        )

        grouped = valid.groupby(
            "imbalance_bucket",
            observed=False,
        )

        summary = grouped.agg(
            observations=(target, "size"),
            mean_imbalance=(feature, "mean"),
            mean_return_bps=(target, "mean"),
            median_return_bps=(target, "median"),
            positive_return_pct=(
                target,
                lambda x: 100 * (x > 0).mean(),
            ),
            negative_return_pct=(
                target,
                lambda x: 100 * (x < 0).mean(),
            ),
            mean_positive_move_bps=(
                target,
                lambda x: x[x > 0].mean(),
            ),
            mean_negative_move_bps=(
                target,
                lambda x: x[x < 0].mean(),
            ),
        )

        print("\n" + "-" * 78)
        print(f"FUTURE RETURN HORIZON: {horizon} SECOND(S)")
        print("-" * 78)
        print(summary.to_string(
            float_format=lambda value: f"{value:.4f}"
        ))

        # Does the mean return mostly reflect a small number of
        # extreme observations? Compare original and winsorised means.
        lower = valid[target].quantile(0.01)
        upper = valid[target].quantile(0.99)
        clipped_returns = valid[target].clip(lower, upper)

        original_mean = valid[target].mean()
        clipped_mean = clipped_returns.mean()

        print(f"\nOverall mean return: {original_mean:.6f} bps")
        print(f"Mean after 1% tail clipping: {clipped_mean:.6f} bps")
        print(f"1st percentile: {lower:.6f} bps")
        print(f"99th percentile: {upper:.6f} bps")


if __name__ == "__main__":
    main()
