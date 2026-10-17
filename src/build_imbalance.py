from pathlib import Path
from zipfile import ZipFile

import pandas as pd


# 1. Locate the raw data we downloaded in Step 1.
zip_path = Path(
    "data/raw/BTCUSDT-aggTrades-2025-06-01.zip"
)

if not zip_path.exists():
    raise FileNotFoundError(
        f"Cannot find {zip_path}. "
        "Run src/download_sample.py from the project root first."
    )

columns = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_is_maker",
    "best_price_match",
]

# 2. Read the CSV directly from the ZIP archive.
with ZipFile(zip_path) as archive:
    csv_files = [
        name for name in archive.namelist()
        if name.endswith(".csv")
    ]

    if not csv_files:
        raise RuntimeError("No CSV file found in the archive.")

    with archive.open(csv_files[0]) as csv_file:
        df = pd.read_csv(
            csv_file,
            header=None,
            names=columns,
        )

# 3. Convert the relevant columns to reliable data types.
df["price"] = pd.to_numeric(df["price"], errors="raise")
df["quantity"] = pd.to_numeric(
    df["quantity"], errors="raise"
)
df["timestamp"] = pd.to_numeric(
    df["timestamp"], errors="raise"
)

maker_flag = (
    df["buyer_is_maker"]
    .astype(str)
    .str.lower()
    .map({"true": True, "false": False})
)

if maker_flag.isna().any():
    raise ValueError("Unexpected values in buyer_is_maker.")

df["buyer_is_maker"] = maker_flag

# Binance spot archives use microseconds for this 2025 data.
timestamp_unit = (
    "us" if df["timestamp"].iloc[0] > 10**14 else "ms"
)

df["timestamp_utc"] = pd.to_datetime(
    df["timestamp"],
    unit=timestamp_unit,
    utc=True,
)

# 4. Give each trade a direction:
#    +quantity when the buyer was aggressive.
#    -quantity when the seller was aggressive.
df["signed_quantity"] = df["quantity"].where(
    ~df["buyer_is_maker"],
    -df["quantity"],
)

# 5. Aggregate all trades into one-second intervals.
df = df.set_index("timestamp_utc").sort_index()

per_second = df.resample("1s").agg(
    close_price=("price", "last"),
    total_qty_btc=("quantity", "sum"),
    signed_qty_btc=("signed_quantity", "sum"),
    trade_count=("agg_trade_id", "count"),
)

# 6. Calculate the imbalance for each second.
# Seconds with no trades have no measurable imbalance,
# so we leave their imbalance undefined (NaN).
nonzero_volume = per_second["total_qty_btc"].where(
    per_second["total_qty_btc"] > 0
)

per_second["flow_imbalance"] = (
    per_second["signed_qty_btc"] / nonzero_volume
)

# 7. Sanity checks: imbalance must be between -1 and +1.
active = per_second["trade_count"] > 0
imbalance = per_second.loc[active, "flow_imbalance"]

assert not imbalance.isna().any()
assert imbalance.between(-1, 1).all()

# 8. Save our processed data separately from the raw archive.
output_dir = Path("data/processed")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / "BTCUSDT-1s-2025-06-01.csv"

per_second.to_csv(
    output_path,
    index_label="timestamp_utc",
)

# 9. Print a research-oriented summary.
print(f"Raw aggregated trades: {len(df):,}")
print(f"One-second intervals: {len(per_second):,}")
print(f"Intervals with trades: {active.sum():,}")
print(f"Intervals without trades: {(~active).sum():,}")

print(
    "\nShare of active seconds with positive imbalance: "
    f"{(imbalance > 0).mean():.2%}"
)
print(
    "Share of active seconds with negative imbalance: "
    f"{(imbalance < 0).mean():.2%}"
)
print(
    "Share of active seconds with zero imbalance: "
    f"{(imbalance == 0).mean():.2%}"
)

print("\nImbalance distribution:")
print(imbalance.describe().round(4))

print("\nFirst 10 active intervals:")
print(
    per_second.loc[
        active,
        [
            "close_price",
            "total_qty_btc",
            "signed_qty_btc",
            "trade_count",
            "flow_imbalance",
        ],
    ].head(10).round(6).to_string()
)

print(f"\nSaved processed data to: {output_path}")
