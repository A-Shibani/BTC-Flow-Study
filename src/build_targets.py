from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "data/processed/BTCUSDT-1s-2025-06-01.csv"
)

OUTPUT_DIR = Path("data/processed")
OUTPUT_PATH = OUTPUT_DIR / "BTCUSDT-targets-2025-06-01.csv"

if not INPUT_PATH.exists():
    raise FileNotFoundError(
        f"Cannot find {INPUT_PATH}. "
        "Run src/build_imbalance.py first."
    )

# 1. Load the processed one-second data.
df = pd.read_csv(INPUT_PATH)

df["timestamp_utc"] = pd.to_datetime(
    df["timestamp_utc"], utc=True
)

df = df.set_index("timestamp_utc").sort_index()

if df.index.has_duplicates:
    raise ValueError("Duplicate timestamps found.")

# 2. Align each observation to the END of its one-second
#    interval. Resample previously labelled bins by their
#    start time, but their features use the whole interval.
df.index = df.index + pd.Timedelta(seconds=1)

# 3. Carry forward the last observed trade price through
#    seconds without trades. Forward fill uses past prices,
#    not future prices.
df["price_ffill"] = df["close_price"].ffill()

if df["price_ffill"].isna().any():
    raise ValueError("Some prices could not be filled.")

# 4. Create future-return targets for each horizon.
#    shift(-h) means the price h rows into the future.
horizons = [1, 5, 30]

for horizon in horizons:
    future_price = df["price_ffill"].shift(-horizon)

    df[f"future_return_{horizon}s_bps"] = (
        future_price / df["price_ffill"] - 1
    ) * 10_000

# 5. Basic validation.
assert df["price_ffill"].gt(0).all()

for horizon in horizons:
    target = df[f"future_return_{horizon}s_bps"]

    # The final h rows cannot have an h-second future target.
    assert target.tail(horizon).isna().all()

# 6. Save the data for subsequent research.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df.to_csv(OUTPUT_PATH, index_label="timestamp_utc")

# 7. Summarise targets using seconds with a measurable
#    flow-imbalance feature and a valid future return.
print(f"Total one-second rows: {len(df):,}")
print(
    "Rows with a measurable imbalance: "
    f"{df['flow_imbalance'].notna().sum():,}"
)

for horizon in horizons:
    feature_and_target = df[
        [
            "flow_imbalance",
            f"future_return_{horizon}s_bps",
        ]
    ].dropna()

    target = feature_and_target[
        f"future_return_{horizon}s_bps"
    ]

    print(f"\n--- {horizon}-second future return ---")
    print(f"Valid feature/target pairs: {len(target):,}")
    print(f"Mean return:   {target.mean():.4f} bps")
    print(f"Median return: {target.median():.4f} bps")
    print(f"Std deviation: {target.std():.4f} bps")

    pearson = feature_and_target.corr(
        method="pearson"
    ).iloc[0, 1]

    spearman = feature_and_target.corr(
        method="spearman"
    ).iloc[0, 1]

    print(f"Pearson correlation:  {pearson:.5f}")
    print(f"Spearman correlation: {spearman:.5f}")

print(f"\nSaved targets to: {OUTPUT_PATH}")
