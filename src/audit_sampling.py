
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "BTCUSDT-targets-2025-06-08_to_2025-06-30.csv"
)


def main():
    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")

    interval_seconds = 5
    sample_mask = (
    df.index.second % interval_seconds == 0
    )

    expected_samples = len(df) // interval_seconds

    print(f"Rows: {len(df):,}")
    print(f"First timestamp: {df.index[0]}")
    print(f"Last timestamp:  {df.index[-1]}")
    print(f"Expected samples: {expected_samples:,}")
    print(f"Actual samples:   {int(sample_mask.sum()):,}")

    gaps = df.index.to_series().diff().dropna()
    print("\nTimestamp intervals:")
    print(gaps.value_counts().head().to_string())

    print("\nSamples per UTC date:")
    sample_dates = pd.Series(
        df.index[sample_mask].strftime("%Y-%m-%d")
    )
    print(sample_dates.value_counts().sort_index().to_string())

    print("\nSignals meeting the frozen thresholds:")
    imbalance = df.loc[sample_mask, "flow_imbalance"]

    signals = (
        (imbalance >= 0.75)
        | (imbalance <= -0.75)
    )
    print(f"{int(signals.sum()):,}")


if __name__ == "__main__":
    main()
