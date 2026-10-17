from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/processed/BTCUSDT-targets-2025-06-01.csv"
)

if not INPUT_PATH.exists():
    raise FileNotFoundError(
        f"Cannot find {INPUT_PATH}. "
        "Run the previous pipeline steps first."
    )

df = pd.read_csv(INPUT_PATH)

# The CSV contains timestamps as well as the feature
# and future-return columns.
if "timestamp_utc" not in df.columns:
    raise ValueError("Expected timestamp_utc column.")

# Divide imbalance into fixed, interpretable ranges.
bins = [
    -1.000001,
    -0.75,
    -0.50,
    -0.25,
    0.00,
    0.25,
    0.50,
    0.75,
    1.000001,
]

horizons = [1, 5, 30]

for horizon in horizons:
    target = f"future_return_{horizon}s_bps"

    sample = df[
        ["flow_imbalance", target]
    ].dropna().copy()

    sample["imbalance_bucket"] = pd.cut(
        sample["flow_imbalance"],
        bins=bins,
        include_lowest=True,
    )

    # Summarise outcomes for each level of trade pressure.
    summary = sample.groupby(
        "imbalance_bucket",
        observed=False,
    ).agg(
        observations=(target, "size"),
        mean_imbalance=("flow_imbalance", "mean"),
        mean_return_bps=(target, "mean"),
        median_return_bps=(target, "median"),
        positive_return_pct=(
            target,
            lambda values: 100 * (values > 0).mean(),
        ),
    )

    print(f"\n{'=' * 65}")
    print(f"Future return horizon: {horizon} seconds")
    print(f"{'=' * 65}")

    print(summary.round(4).to_string())

    # Check whether a small number of large returns may be
    # influencing the Pearson correlation.
    pearson = sample["flow_imbalance"].corr(
        sample[target],
        method="pearson",
    )

    lower, upper = sample[target].quantile([0.01, 0.99])

    clipped_returns = sample[target].clip(
        lower=lower,
        upper=upper,
    )

    clipped_pearson = sample["flow_imbalance"].corr(
        clipped_returns,
        method="pearson",
    )

    spearman = sample["flow_imbalance"].corr(
        sample[target],
        method="spearman",
    )

    print(f"\nPearson correlation: {pearson:.5f}")
    print(f"Spearman correlation: {spearman:.5f}")
    print(
        "Pearson after clipping the most extreme 1% "
        f"at each tail: {clipped_pearson:.5f}"
    )
