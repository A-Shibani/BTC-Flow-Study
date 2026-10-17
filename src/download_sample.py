from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import requests


SYMBOL = "BTCUSDT"
DATE = "2025-06-01"

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

url = (
    "https://data.binance.vision/data/spot/daily/"
    f"aggTrades/{SYMBOL}/{SYMBOL}-aggTrades-{DATE}.zip"
)

zip_path = DATA_DIR / f"{SYMBOL}-aggTrades-{DATE}.zip"

print(f"Downloading {SYMBOL} data for {DATE}...")

response = requests.get(url, timeout=90)
response.raise_for_status()

zip_path.write_bytes(response.content)

print(f"Saved archive: {zip_path}")
print(f"Downloaded {len(response.content):,} bytes")

# Read the CSV stored inside the ZIP archive.
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

with ZipFile(BytesIO(response.content)) as archive:
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

# Convert numeric fields to numeric data types.
df["price"] = pd.to_numeric(df["price"], errors="raise")
df["quantity"] = pd.to_numeric(df["quantity"], errors="raise")
df["timestamp"] = pd.to_numeric(df["timestamp"], errors="raise")

# Binance's spot archive uses microsecond timestamps from 2025 onward.
timestamp_unit = "us" if df["timestamp"].iloc[0] > 10**14 else "ms"

df["timestamp_utc"] = pd.to_datetime(
    df["timestamp"],
    unit=timestamp_unit,
    utc=True,
)

# Basic data-quality checks.
print(f"\nRows: {len(df):,}")
print(f"Missing values:\n{df.isna().sum()}")
print(f"\nFirst timestamp: {df['timestamp_utc'].min()}")
print(f"Last timestamp:  {df['timestamp_utc'].max()}")
print("\nFirst five rows:")
print(df.head().to_string(index=False))
