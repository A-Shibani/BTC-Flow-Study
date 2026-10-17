from datetime import date, timedelta
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd


# --------------------------------------------------
# Configuration
# --------------------------------------------------

SYMBOL = "BTCUSDT"
START_DATE = date(2026, 9, 1)
END_DATE = date(2026, 9, 30)

SECONDS_PER_DAY = 86_400
HORIZONS = (1, 5, 30)

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

COLUMNS = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_is_maker",
    "best_price_match",
]


def dates_in_range():
    """Return every calendar date, including both endpoints."""
    current = START_DATE
    while current <= END_DATE:
        yield current
        current += timedelta(days=1)


def build_one_day(day: date) -> pd.DataFrame:
    """Convert one Binance aggregate-trade archive into 1-second bars."""

    filename = f"{SYMBOL}-aggTrades-{day:%Y-%m-%d}.zip"
    archive_path = RAW_DIR / filename

    if not archive_path.exists():
        raise FileNotFoundError(
            f"Missing archive: {archive_path}. Run the downloader first."
        )

    with ZipFile(archive_path) as archive:
        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        if len(csv_files) != 1:
            raise ValueError(
                f"Expected one CSV inside {filename}; found {len(csv_files)}."
            )

        with archive.open(csv_files[0]) as csv_file:
            trades = pd.read_csv(
                csv_file,
                header=None,
                names=COLUMNS,
                usecols=[
                    "price",
                    "quantity",
                    "timestamp",
                    "buyer_is_maker",
                ],
                dtype={
                    "price": "float64",
                    "quantity": "float64",
                    "timestamp": "int64",
                },
            )

    if trades.empty:
        raise ValueError(f"No trade data found in {filename}.")

    # Binance timestamps in this dataset are in microseconds.
    trades["timestamp"] = pd.to_datetime(
        trades["timestamp"],
        unit="us",
        utc=True,
        errors="coerce",
    )

    if trades["timestamp"].isna().any():
        raise ValueError(f"Invalid timestamps found in {filename}.")

    # Check that the archive really contains the expected UTC date.
    if not (trades["timestamp"].dt.date == day).all():
        raise ValueError(
            f"Timestamps in {filename} do not all match {day} UTC."
        )

    # True means the buyer was the passive maker, so the seller
    # initiated the trade. Aggressive buying therefore has positive sign.
    maker_flag = (
        trades["buyer_is_maker"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )

    if maker_flag.isna().any():
        raise ValueError(
            f"Could not interpret buyer_is_maker in {filename}."
        )

    trades["signed_qty_btc"] = np.where(
        maker_flag,
        -trades["quantity"],
        trades["quantity"],
    )

    trades = trades.set_index("timestamp").sort_index()

    # Each bar is labelled by the UTC second in which it starts.
    bars = trades.resample("1s").agg(
        close_price=("price", "last"),
        total_qty_btc=("quantity", "sum"),
        signed_qty_btc=("signed_qty_btc", "sum"),
        trade_count=("price", "size"),
    )

    # Keep every second, even when no trades occurred.
    day_index = pd.date_range(
        start=pd.Timestamp(day.isoformat(), tz="UTC"),
        periods=SECONDS_PER_DAY,
        freq="s",
    )
    bars = bars.reindex(day_index)
    bars.index.name = "bar_start_utc"

    # No-trade seconds have zero volume and zero trade count.
    # Their flow imbalance remains NaN because there was no traded flow.
    bars["total_qty_btc"] = bars["total_qty_btc"].fillna(0.0)
    bars["signed_qty_btc"] = bars["signed_qty_btc"].fillna(0.0)
    bars["trade_count"] = bars["trade_count"].fillna(0).astype("int64")

    denominator = bars["total_qty_btc"].replace(0, np.nan)
    bars["flow_imbalance"] = bars["signed_qty_btc"] / denominator

    print(
        f"{day}: {len(trades):,} raw trades; "
        f"{int((bars['trade_count'] > 0).sum()):,} active seconds"
    )

    return bars


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    daily_bars = [
        build_one_day(day)
        for day in dates_in_range()
    ]

    # Combine all requested daily dataframes chronologically.
    bars = pd.concat(daily_bars).sort_index()

    expected_index = pd.date_range(
        start=pd.Timestamp(START_DATE.isoformat(), tz="UTC"),
        periods=(END_DATE - START_DATE).days * SECONDS_PER_DAY
        + SECONDS_PER_DAY,
        freq="s",
    )

    if len(bars) != len(expected_index):
        raise ValueError(
            f"Expected {len(expected_index):,} seconds; got {len(bars):,}."
        )

    if not bars.index.equals(expected_index):
        raise ValueError("Combined timestamps are missing or duplicated.")

    bars_path = (
        PROCESSED_DIR
        / f"{SYMBOL}-1s-{START_DATE}_to_{END_DATE}.csv"
    )
    bars.to_csv(bars_path, index_label="bar_start_utc")

    # The complete bar's features become known at its END, not its start.
    # Shift the index by one second before defining future-return targets.
    dataset = bars.copy()
    dataset.index = dataset.index + pd.Timedelta(seconds=1)
    dataset.index.name = "feature_available_at_utc"

    # Carry the last traded price across seconds with no trades.
    # Keep the original close_price column unchanged for data inspection.
    known_price = dataset["close_price"].ffill()

    for horizon in HORIZONS:
        future_price = known_price.shift(-horizon)
        dataset[f"future_return_{horizon}s_bps"] = (
            future_price / known_price - 1
        ) * 10_000

    targets_path = (
        PROCESSED_DIR
        / f"{SYMBOL}-targets-{START_DATE}_to_{END_DATE}.csv"
    )
    dataset.to_csv(targets_path, index_label="feature_available_at_utc")

    # Count and inspect the observations actually usable for each target.
    print("\n" + "=" * 68)
    print("DATASET SUMMARY")
    print("=" * 68)
    print(f"Total one-second bars: {len(bars):,}")
    print(f"Seconds with trades: {(bars['trade_count'] > 0).sum():,}")
    print(f"Seconds without trades: {(bars['trade_count'] == 0).sum():,}")
    print(f"Bars CSV: {bars_path}")
    print(f"Targets CSV: {targets_path}")

    print("\nPOOLED CORRELATIONS — EXPLORATORY ONLY")
    print("horizon | observations | Pearson | Spearman")

    for horizon in HORIZONS:
        target_col = f"future_return_{horizon}s_bps"
        valid = dataset[["flow_imbalance", target_col]].dropna()

        pearson = valid["flow_imbalance"].corr(
            valid[target_col], method="pearson"
        )
        spearman = valid["flow_imbalance"].corr(
            valid[target_col], method="spearman"
        )

        print(
            f"{horizon:>7}s | {len(valid):>12,} | "
            f"{pearson:>7.4f} | {spearman:>8.4f}"
        )

    # Group using the original bar's date, not the shifted availability
    # timestamp, so the last bar of each day stays with that day.
    original_bar_date = (
        dataset.index - pd.Timedelta(seconds=1)
    ).date

    print("\nDAILY PEARSON CORRELATIONS")
    print("date       | 1-second | 5-second | 30-second")

    for day in dates_in_range():
        mask = original_bar_date == day
        results = []

        for horizon in HORIZONS:
            target_col = f"future_return_{horizon}s_bps"
            valid = dataset.loc[
                mask, ["flow_imbalance", target_col]
            ].dropna()

            corr = valid["flow_imbalance"].corr(
                valid[target_col], method="pearson"
            )
            results.append(corr)

        formatted = " | ".join(
            f"{value:>8.4f}" if pd.notna(value) else "     NaN"
            for value in results
        )
        print(f"{day} | {formatted}")


if __name__ == "__main__":
    main()
