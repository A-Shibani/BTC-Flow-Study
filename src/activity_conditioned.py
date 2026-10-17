"""Activity-conditioned diagnostics for the BTCUSDT OFI study.

Keeps the original OFI thresholds, decision grid, entry delay and holding period fixed and
reports pre-declared trade-count filters as sensitivity analyses.
"""

from pathlib import Path
import numpy as np
import pandas as pd

START_DATE = "2025-06-01"
END_DATE = "2025-06-07"
LONG_THRESHOLD = 0.75
SHORT_THRESHOLD = -0.75
SIGNAL_INTERVAL_SECONDS = 5
ENTRY_DELAY_SECONDS = 1
HOLD_SECONDS = 5
# Pre-declared sensitivity checks: these are not selected to maximise return.
MIN_TRADE_COUNTS = (0, 2, 5, 10)
COST_SCENARIOS_BPS = (0.0, 0.1, 1.0, 3.0, 10.0, 20.0)

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR / "data" / "processed"
    / f"BTCUSDT-targets-{START_DATE}_to_{END_DATE}.csv"
)
OUTPUT_DIR = PROJECT_DIR / "reports"


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Development dataset not found: {DATA_PATH}")
    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")
    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        raise ValueError("Expected timezone-aware feature_available_at_utc timestamps.")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("Timestamps must be sorted and unique.")
    if len(df) != 7 * 86_400:
        raise ValueError(f"Expected 604,800 rows; got {len(df):,}.")
    steps = df.index.to_series().diff().dropna()
    if not (steps == pd.Timedelta(seconds=1)).all():
        raise ValueError("Expected a continuous one-second timestamp grid.")
    required = {"flow_imbalance", "trade_count", "total_qty_btc", "close_price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {sorted(missing)}")
    return df


def build_decisions(df: pd.DataFrame) -> pd.DataFrame:
    """Create the same decision/trade alignment as the frozen baseline."""
    # With UTC timestamps, .second selects seconds 00,05,...,55 every minute.
    mask = (df.index.second % SIGNAL_INTERVAL_SECONDS) == 0
    decisions = df.loc[mask, [
        "flow_imbalance", "trade_count", "total_qty_btc", "close_price"
    ]].copy()
    if len(decisions) != len(df) // SIGNAL_INTERVAL_SECONDS:
        raise ValueError("Unexpected number of five-second decision timestamps.")

    # These price proxies use known last-trade prices, forward-filled over
    # no-trade seconds. They are not executable bid/ask prices.
    mark_price = df["close_price"].ffill()
    entry_price = mark_price.shift(-ENTRY_DELAY_SECONDS)
    exit_price = mark_price.shift(-(ENTRY_DELAY_SECONDS + HOLD_SECONDS))
    decisions["entry_price"] = entry_price.loc[decisions.index]
    decisions["exit_price"] = exit_price.loc[decisions.index]

    ofi = decisions["flow_imbalance"]
    decisions["direction"] = np.select(
        [ofi >= LONG_THRESHOLD, ofi <= SHORT_THRESHOLD],
        [1, -1],
        default=0,
    ).astype(int)
    decisions["is_signal"] = decisions["direction"] != 0
    decisions["date"] = decisions.index.strftime("%Y-%m-%d")

    valid_prices = (
        decisions["entry_price"].notna()
        & decisions["exit_price"].notna()
        & (decisions["entry_price"] > 0)
        & (decisions["exit_price"] > 0)
    )
    decisions["valid_prices"] = valid_prices
    underlying = decisions["exit_price"] / decisions["entry_price"] - 1.0
    decisions["gross_return_bps"] = (
        decisions["direction"] * underlying * 10_000
    )
    decisions.loc[~valid_prices, "gross_return_bps"] = np.nan
    decisions.loc[~decisions["is_signal"], "gross_return_bps"] = np.nan
    return decisions


def summarise_variant(decisions: pd.DataFrame, min_trade_count: int) -> dict:
    eligible = decisions[decisions["trade_count"] >= min_trade_count]
    signals = eligible[eligible["is_signal"]]
    trades = signals[signals["valid_prices"]].copy()
    returns = trades["gross_return_bps"].dropna().astype(float)

    result = {
        "min_trade_count_filter": min_trade_count,
        "decision_timestamps": len(decisions),
        "eligible_decisions": len(eligible),
        "eligible_decision_pct": 100 * len(eligible) / len(decisions),
        "signal_count": int(eligible["is_signal"].sum()),
        "signal_rate_all_decisions_pct": 100 * int(eligible["is_signal"].sum()) / len(decisions),
        "signal_rate_eligible_decisions_pct": 100 * int(eligible["is_signal"].sum()) / len(eligible) if len(eligible) else np.nan,
        "valid_trades": len(returns),
        "mean_gross_bps": returns.mean() if len(returns) else np.nan,
        "median_gross_bps": returns.median() if len(returns) else np.nan,
        "gross_win_rate_pct": 100 * (returns > 0).mean() if len(returns) else np.nan,
        "zero_return_rate_pct": 100 * (returns == 0).mean() if len(returns) else np.nan,
        "trimmed_mean_1pct_each_tail_bps": returns.sort_values().iloc[
            int(np.floor(0.01 * len(returns))): len(returns) - int(np.floor(0.01 * len(returns)))
        ].mean() if len(returns) >= 100 else np.nan,
    }
    for cost in COST_SCENARIOS_BPS:
        result[f"net_mean_at_{cost:g}bps_cost"] = (
            returns.mean() - cost if len(returns) else np.nan
        )
    return result


def activity_bucket_summary(decisions: pd.DataFrame) -> pd.DataFrame:
    bins = [-0.5, 0.5, 1.5, 5.5, 20.5, np.inf]
    labels = ["0 trades", "1 trade", "2-5 trades", "6-20 trades", ">20 trades"]
    out = decisions.copy()
    out["activity_bucket"] = pd.cut(
        out["trade_count"].fillna(0), bins=bins, labels=labels,
        include_lowest=True,
    )
    grouped = out.groupby("activity_bucket", observed=False)
    summary = grouped.agg(
        decision_count=("is_signal", "size"),
        signal_count=("is_signal", "sum"),
        median_btc_volume=("total_qty_btc", "median"),
        mean_btc_volume=("total_qty_btc", "mean"),
        median_abs_ofi=("flow_imbalance", lambda x: x.abs().median()),
    )
    summary["signal_rate_pct"] = 100 * summary["signal_count"] / summary["decision_count"]
    return summary.reset_index()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    decisions = build_decisions(df)

    print("=" * 84)
    print("ACTIVITY-CONDITIONED OFI CHECK — JUNE 1-7 DEVELOPMENT DATA")
    print("=" * 84)
    print(f"Rows loaded: {len(df):,}; decision timestamps: {len(decisions):,}")
    print("Frozen thresholds: long OFI >= 0.75; short OFI <= -0.75")
    print("Fixed timing: 5-second grid, 1-second entry delay, 5-second hold")
    print("Price proxy: forward-filled last trade price; not executable bid/ask quotes")

    activity = activity_bucket_summary(decisions)
    print("\nSIGNAL FREQUENCY BY FEATURE-BAR TRADE COUNT")
    print(activity.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    activity.to_csv(OUTPUT_DIR / "activity_bucket_summary_june_2025.csv", index=False)

    rows = [summarise_variant(decisions, threshold) for threshold in MIN_TRADE_COUNTS]
    results = pd.DataFrame(rows)
    print("\nPRE-DECLARED ACTIVITY-FILTER SENSITIVITY")
    print("Filters do not change OFI thresholds, decision grid, entry or exit timing.")
    print(results.to_string(index=False, float_format=lambda x: f"{x:.5f}"))
    results.to_csv(OUTPUT_DIR / "activity_filter_sensitivity_june_2025.csv", index=False)

    # Side-level results, baseline and each activity filter.
    side_rows = []
    for min_count in MIN_TRADE_COUNTS:
        eligible = decisions[
            (decisions["trade_count"] >= min_count)
            & decisions["is_signal"]
            & decisions["valid_prices"]
        ].copy()
        for side, direction in [("LONG", 1), ("SHORT", -1)]:
            returns = eligible.loc[eligible["direction"] == direction, "gross_return_bps"].dropna()
            side_rows.append({
                "min_trade_count_filter": min_count,
                "side": side,
                "trades": len(returns),
                "mean_gross_bps": returns.mean() if len(returns) else np.nan,
                "win_rate_pct": 100 * (returns > 0).mean() if len(returns) else np.nan,
            })
    side_df = pd.DataFrame(side_rows)
    side_df.to_csv(OUTPUT_DIR / "activity_filter_long_short_june_2025.csv", index=False)
    print("\nLONG / SHORT RESULTS BY FILTER")
    print(side_df.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    print("\nSaved reports:")
    print(f"  {OUTPUT_DIR / 'activity_bucket_summary_june_2025.csv'}")
    print(f"  {OUTPUT_DIR / 'activity_filter_sensitivity_june_2025.csv'}")
    print(f"  {OUTPUT_DIR / 'activity_filter_long_short_june_2025.csv'}")
    print("\nInterpretation caution: these are pre-declared development diagnostics, not a new optimized strategy.")


if __name__ == "__main__":
    main()
