"""Exploratory diagnostics for the BTCUSDT order-flow study.

Expected input:
    data/processed/BTCUSDT-targets-2025-06-01_to_2025-06-07.csv

Outputs are written to reports/ and reports/figures/.
"""

from __future__ import annotations

from pathlib import Path
import math
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Frozen paths and descriptive strategy settings
# ---------------------------------------------------------------------
START_DATE = "2025-06-01"
END_DATE = "2025-06-07"
HORIZONS = (1, 5, 30)

# Use the rule already tested in our preliminary backtests. This script
# diagnoses it; it does not optimise these parameters.
SIGNAL_INTERVAL_SECONDS = 5
LONG_THRESHOLD = 0.75
SHORT_THRESHOLD = -0.75
ENTRY_DELAY_SECONDS = 1
HOLD_SECONDS = 5

IMBALANCE_BINS = [
    -1.000001, -0.75, -0.50, -0.25,
    0.0, 0.25, 0.50, 0.75, 1.000001,
]
IMBALANCE_LABELS = [
    "[-1, -0.75]", "(-0.75, -0.50]", "(-0.50, -0.25]",
    "(-0.25, 0]", "(0, 0.25]", "(0.25, 0.50]",
    "(0.50, 0.75]", "(0.75, 1]",
]

PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / f"BTCUSDT-targets-{START_DATE}_to_{END_DATE}.csv"
)
REPORT_DIR = PROJECT_DIR / "reports"
FIGURE_DIR = REPORT_DIR / "figures"


# ---------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------
def load_development_data() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Could not find development dataset:\n{INPUT_PATH}\n"
            "Check the filename/date range, and do not substitute the holdout data."
        )

    df = pd.read_csv(
        INPUT_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")
    df = df.sort_index()

    required = {
        "flow_imbalance", "close_price", "total_qty_btc", "signed_qty_btc",
        "trade_count", "future_return_1s_bps", "future_return_5s_bps",
        "future_return_30s_bps",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Dataset is missing required columns: {sorted(missing)}.\n"
            "Expected the targets file produced by build_multiday_dataset.py."
        )

    if df.index.has_duplicates:
        raise ValueError("Duplicate feature timestamps found.")
    if not df.index.is_monotonic_increasing:
        raise ValueError("Feature timestamps are not in chronological order.")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Expected a DatetimeIndex after parsing timestamps.")
    if df.index.tz is None:
        raise ValueError("Timestamps must include timezone information (UTC).")

    # Timestamps were shifted by one second so that the full bar's feature
    # represents information available at the timestamp. Confirm this file
    # corresponds to the development window, assigning each row back to its
    # original bar time for daily grouping.
    original_bar_time = df.index - pd.Timedelta(seconds=1)
    row_dates = pd.Index(original_bar_time.strftime("%Y-%m-%d"))
    observed_dates = set(row_dates)
    expected_dates = set(pd.date_range(START_DATE, END_DATE, freq="D").strftime("%Y-%m-%d"))
    if observed_dates != expected_dates:
        raise ValueError(
            "Input dates do not match the intended development period. "
            f"Expected {sorted(expected_dates)}, got {sorted(observed_dates)}."
        )

    return df


def ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, filename: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / filename, dpi=180, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------
# 1) OFI bucket summaries and figure
# ---------------------------------------------------------------------
def make_bucket_summary(df: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for horizon in HORIZONS:
        target = f"future_return_{horizon}s_bps"
        valid = df[["flow_imbalance", target]].replace(
            [np.inf, -np.inf], np.nan
        ).dropna().copy()
        valid["ofi_bucket"] = pd.cut(
            valid["flow_imbalance"],
            bins=IMBALANCE_BINS,
            labels=IMBALANCE_LABELS,
            include_lowest=True,
            right=True,
        )

        summary = valid.groupby("ofi_bucket", observed=False).agg(
            observations=(target, "size"),
            mean_ofi=("flow_imbalance", "mean"),
            mean_return_bps=(target, "mean"),
            median_return_bps=(target, "median"),
            positive_return_pct=(target, lambda s: 100 * (s > 0).mean()),
            zero_return_pct=(target, lambda s: 100 * (s == 0).mean()),
        ).reset_index()
        summary.insert(0, "horizon_seconds", horizon)
        pieces.append(summary)

    result = pd.concat(pieces, ignore_index=True)
    result.to_csv(REPORT_DIR / "diagnostics_ofi_bucket_summary.csv", index=False)

    # Separate panel per horizon avoids visual comparison problems due to
    # very different return scales.
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    x = np.arange(len(IMBALANCE_LABELS))
    for ax, horizon in zip(axes, HORIZONS):
        part = result[result["horizon_seconds"] == horizon].set_index("ofi_bucket")
        means = part["mean_return_bps"].reindex(IMBALANCE_LABELS)
        ax.bar(x, means.values)
        ax.axhline(0, linewidth=1, color="black")
        ax.set_ylabel("Mean future return (bps)")
        ax.set_title(f"Future return over {horizon}s")
        ax.grid(axis="y", alpha=0.25)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(IMBALANCE_LABELS, rotation=25, ha="right")
    fig.suptitle("June 1–7 development sample: future returns by OFI bucket", y=1.01)
    save_figure(fig, "01_ofi_bucket_means.png")
    return result


# ---------------------------------------------------------------------
# 2) Return distributions, correlation diagnostics and histogram figure
# ---------------------------------------------------------------------
def make_return_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fig, axes = plt.subplots(3, 1, figsize=(10, 11))

    for ax, horizon in zip(axes, HORIZONS):
        target = f"future_return_{horizon}s_bps"
        valid = df[["flow_imbalance", target]].replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        returns = valid[target].astype(float)
        q01, q99 = returns.quantile([0.01, 0.99])
        shown_outside = 100 * ((returns < q01) | (returns > q99)).mean()

        pearson = valid["flow_imbalance"].corr(returns, method="pearson")
        spearman = valid["flow_imbalance"].corr(returns, method="spearman")
        nonzero = valid.loc[returns != 0]
        spearman_nonzero = (
            nonzero["flow_imbalance"].corr(nonzero[target], method="spearman")
            if len(nonzero) > 1 else np.nan
        )

        # Histograms use all values but limit the display to the 1st–99th
        # percentile range; tails remain in the saved stats and aren't deleted.
        ax.hist(returns.to_numpy(), bins=120, range=(q01, q99))
        ax.set_xlim(q01, q99)
        ax.set_title(
            f"{horizon}s returns | zero={100 * (returns == 0).mean():.1f}% | "
            f"1st–99th percentile view excludes {shown_outside:.1f}% of tails"
        )
        ax.set_xlabel("Future return (bps)")
        ax.set_ylabel("Count")
        ax.grid(axis="y", alpha=0.25)

        rows.append({
            "horizon_seconds": horizon,
            "observations": int(len(returns)),
            "zero_return_pct": 100 * (returns == 0).mean(),
            "positive_return_pct": 100 * (returns > 0).mean(),
            "negative_return_pct": 100 * (returns < 0).mean(),
            "mean_return_bps": returns.mean(),
            "median_return_bps": returns.median(),
            "std_return_bps": returns.std(),
            "p01_return_bps": q01,
            "p99_return_bps": q99,
            "pearson_ofi_return": pearson,
            "spearman_ofi_return": spearman,
            "spearman_nonzero_returns_only": spearman_nonzero,
        })

    fig.suptitle("June 1–7 development sample: forward-return distributions", y=1.01)
    save_figure(fig, "02_forward_return_histograms.png")
    summary = pd.DataFrame(rows)
    summary.to_csv(REPORT_DIR / "diagnostics_return_distribution.csv", index=False)
    return summary


# ---------------------------------------------------------------------
# 3) Daily mean forward returns figure
# ---------------------------------------------------------------------
def make_daily_means(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["original_bar_date"] = (
        work.index - pd.Timedelta(seconds=1)
    ).strftime("%Y-%m-%d")

    rows = []
    for day, group in work.groupby("original_bar_date", sort=True):
        # This loop is kept simple and explicit to make the output easy to audit.
        for h in HORIZONS:
            col = f"future_return_{h}s_bps"
            values = group[col].replace([np.inf, -np.inf], np.nan).dropna()
            rows.append({
                "date": day,
                "horizon_seconds": h,
                "observations": int(values.size),
                "mean_return_bps": values.mean(),
                "median_return_bps": values.median(),
                "positive_return_pct": 100 * (values > 0).mean(),
            })

    result = pd.DataFrame(rows)
    result.to_csv(REPORT_DIR / "diagnostics_daily_means.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    for ax, horizon in zip(axes, HORIZONS):
        part = result[result["horizon_seconds"] == horizon].copy()
        ax.plot(part["date"], part["mean_return_bps"], marker="o", linewidth=1.5)
        ax.axhline(0, linewidth=1, color="black")
        ax.set_ylabel("Mean return (bps)")
        ax.set_title(f"{horizon}s horizon")
        ax.grid(axis="y", alpha=0.25)
    axes[-1].tick_params(axis="x", rotation=30)
    fig.suptitle("Daily mean forward returns: June 1–7 development sample", y=1.01)
    save_figure(fig, "03_daily_mean_forward_returns.png")
    return result


# ---------------------------------------------------------------------
# Strategy signals for descriptive diagnostics only
# ---------------------------------------------------------------------
def build_development_strategy_trades(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mark_price = df["close_price"].ffill()
    entry_price = mark_price.shift(-ENTRY_DELAY_SECONDS)
    exit_price = mark_price.shift(-(ENTRY_DELAY_SECONDS + HOLD_SECONDS))

    # Index is the availability time of the completed preceding bar.
    sample_mask = df.index.second % SIGNAL_INTERVAL_SECONDS == 0
    sampled = df.loc[sample_mask, [
        "flow_imbalance", "trade_count", "total_qty_btc", "signed_qty_btc"
    ]].copy()
    sampled["entry_price"] = entry_price.loc[sampled.index]
    sampled["exit_price"] = exit_price.loc[sampled.index]
    sampled["direction"] = np.select(
        [
            sampled["flow_imbalance"] >= LONG_THRESHOLD,
            sampled["flow_imbalance"] <= SHORT_THRESHOLD,
        ],
        [1, -1],
        default=0,
    )
    sampled["original_bar_date"] = (
        sampled.index - pd.Timedelta(seconds=1)
    ).strftime("%Y-%m-%d")

    signalled = sampled[sampled["direction"] != 0].copy()
    prices_valid = (
        signalled["entry_price"].notna()
        & signalled["exit_price"].notna()
        & (signalled["entry_price"] > 0)
        & (signalled["exit_price"] > 0)
    )
    trades = signalled.loc[prices_valid].copy()
    trades["underlying_return_bps"] = (
        trades["exit_price"] / trades["entry_price"] - 1
    ) * 10_000
    trades["gross_return_bps"] = (
        trades["direction"] * trades["underlying_return_bps"]
    )
    trades["side"] = np.where(trades["direction"] == 1, "LONG", "SHORT")
    trades["signal_time_utc"] = trades.index.astype(str)
    trades.to_csv(REPORT_DIR / "diagnostics_development_strategy_trades.csv", index=False)
    return sampled, trades


def make_activity_breakdown(sampled: pd.DataFrame) -> pd.DataFrame:
    # Trade count and volume refer to the same completed one-second bar from
    # which flow_imbalance was computed. This directly tests whether extreme
    # ratios are disproportionately generated by very thin seconds.
    categories = pd.cut(
        sampled["trade_count"].fillna(0),
        bins=[-1, 0, 1, 5, 20, np.inf],
        labels=["0 trades", "1 trade", "2–5 trades", "6–20 trades", ">20 trades"],
        right=True,
        include_lowest=True,
    )
    activity = sampled.copy()
    activity["activity_bucket"] = categories
    activity["is_signal"] = activity["direction"] != 0
    result = activity.groupby("activity_bucket", observed=False).agg(
        decision_count=("direction", "size"),
        signal_count=("is_signal", "sum"),
        signal_rate_pct=("is_signal", lambda s: 100 * s.mean()),
        median_btc_volume=("total_qty_btc", "median"),
        mean_btc_volume=("total_qty_btc", "mean"),
        median_abs_ofi=("flow_imbalance", lambda s: s.abs().median()),
    ).reset_index()
    result.to_csv(REPORT_DIR / "diagnostics_signal_frequency_by_trade_count.csv", index=False)
    return result


def make_strategy_tail_statistics(trades: pd.DataFrame) -> pd.DataFrame:
    r = trades["gross_return_bps"].astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if r.empty:
        raise ValueError("The strategy has no valid trades in the development sample.")

    q01, q99 = r.quantile([0.01, 0.99])
    q05, q95 = r.quantile([0.05, 0.95])
    trimmed_1 = r[(r >= q01) & (r <= q99)]
    trimmed_5 = r[(r >= q05) & (r <= q95)]
    winsor_1 = r.clip(q01, q99)
    winsor_5 = r.clip(q05, q95)

    n_top = max(1, int(math.ceil(0.01 * len(r))))
    top_1 = r.nlargest(n_top)
    bottom_1 = r.nsmallest(n_top)
    total_pnl_bps = float(r.sum())

    day_returns = trades.groupby("original_bar_date")["gross_return_bps"].agg(["sum", "mean", "size"])
    best_day = day_returns["sum"].idxmax()
    best_day_pnl = float(day_returns.loc[best_day, "sum"])

    def pct_of_total(value: float) -> float:
        # May exceed 100% or be negative when positive and negative P&L offset.
        return 100 * value / total_pnl_bps if total_pnl_bps != 0 else np.nan

    metrics = [
        ("trade_count", float(len(r)), "count"),
        ("mean_gross_return_bps", float(r.mean()), "bps per trade"),
        ("median_gross_return_bps", float(r.median()), "bps per trade"),
        ("win_rate_pct", float(100 * (r > 0).mean()), "% of trades"),
        ("zero_return_rate_pct", float(100 * (r == 0).mean()), "% of trades"),
        ("mean_positive_return_bps", float(r[r > 0].mean()), "bps; winners only"),
        ("mean_negative_return_bps", float(r[r < 0].mean()), "bps; losers only"),
        ("trimmed_mean_1pct_each_tail_bps", float(trimmed_1.mean()), "bps per trade"),
        ("trimmed_mean_5pct_each_tail_bps", float(trimmed_5.mean()), "bps per trade"),
        ("winsorized_mean_1pct_each_tail_bps", float(winsor_1.mean()), "bps per trade"),
        ("winsorized_mean_5pct_each_tail_bps", float(winsor_5.mean()), "bps per trade"),
        ("p01_gross_return_bps", float(q01), "bps"),
        ("p99_gross_return_bps", float(q99), "bps"),
        ("top_1pct_trades_pnl_bps_sum", float(top_1.sum()), "sum of trade returns; bps units"),
        ("top_1pct_trades_share_of_total_pnl_pct", pct_of_total(float(top_1.sum())), "%; may exceed 100%"),
        ("bottom_1pct_trades_pnl_bps_sum", float(bottom_1.sum()), "sum of trade returns; bps units"),
        ("bottom_1pct_trades_share_of_total_pnl_pct", pct_of_total(float(bottom_1.sum())), "%; may be negative"),
        ("total_gross_pnl_bps_sum", total_pnl_bps, "sum of per-trade bps; not account return"),
        ("best_gross_pnl_day", best_day_pnl, f"sum of per-trade bps on {best_day}"),
        ("best_day_share_of_total_pnl_pct", pct_of_total(best_day_pnl), "%; may exceed 100%"),
    ]
    result = pd.DataFrame(metrics, columns=["metric", "value", "interpretation"])
    result.to_csv(REPORT_DIR / "diagnostics_strategy_tail_statistics.csv", index=False)

    # Strategy trade return histogram, visually limiting the x-axis to p1-p99.
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(r.to_numpy(), bins=120, range=(q01, q99))
    ax.axvline(0, linewidth=1.2, color="black")
    ax.axvline(r.mean(), linestyle="--", linewidth=1.5, label=f"Mean = {r.mean():.4f} bps")
    ax.axvline(r.median(), linestyle=":", linewidth=1.5, label=f"Median = {r.median():.4f} bps")
    outside_pct = 100 * ((r < q01) | (r > q99)).mean()
    ax.set_title(
        "June 1–7 strategy gross returns "
        f"(display limited to p1–p99; {outside_pct:.1f}% of observations in tails)"
    )
    ax.set_xlabel("Gross return per simulated trade (bps)")
    ax.set_ylabel("Trade count")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    save_figure(fig, "04_strategy_trade_return_histogram.png")
    return result


def make_cost_curve(trades: pd.DataFrame) -> pd.DataFrame:
    gross = trades["gross_return_bps"].astype(float).dropna()
    mean_gross = float(gross.mean())
    costs = np.linspace(0, 20, 401)
    result = pd.DataFrame({"round_trip_cost_bps": costs})
    result["mean_net_return_bps_per_trade"] = mean_gross - result["round_trip_cost_bps"]
    result["break_even_cost_bps"] = mean_gross
    result.to_csv(REPORT_DIR / "diagnostics_cost_curve.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(result["round_trip_cost_bps"], result["mean_net_return_bps_per_trade"], linewidth=2)
    ax.axhline(0, linewidth=1.2, color="black")
    ax.axvline(mean_gross, linestyle="--", linewidth=1.5,
               label=f"Break-even = {mean_gross:.4f} bps")
    ax.set_xlabel("Assumed all-in round-trip cost (bps of notional)")
    ax.set_ylabel("Mean net return per trade (bps)")
    ax.set_title("Cost sensitivity: frozen rule, June 1–7 development sample")
    ax.grid(alpha=0.25)
    ax.legend()
    save_figure(fig, "05_strategy_cost_curve.png")
    return result


def write_text_summary(
    df: pd.DataFrame,
    distribution: pd.DataFrame,
    sampled: pd.DataFrame,
    trades: pd.DataFrame,
    activity: pd.DataFrame,
    tails: pd.DataFrame,
) -> None:
    original_dates = (df.index - pd.Timedelta(seconds=1)).strftime("%Y-%m-%d")
    signal_count = int((sampled["direction"] != 0).sum())
    valid_trade_count = len(trades)
    invalid_signal_count = signal_count - valid_trade_count

    lines = [
        "JUNE 1-7 DEVELOPMENT-SAMPLE DIAGNOSTICS",
        "=" * 54,
        f"Input: {INPUT_PATH.name}",
        f"Rows: {len(df):,}",
        f"Original bar dates: {min(original_dates)} to {max(original_dates)}",
        "",
        "Forward-return correlations and distributions:",
        distribution.to_string(index=False, float_format=lambda x: f"{x:.6f}"),
        "",
        "Frozen strategy settings (diagnostic only):",
        f"OFI long threshold: >= {LONG_THRESHOLD}",
        f"OFI short threshold: <= {SHORT_THRESHOLD}",
        f"Signal interval: {SIGNAL_INTERVAL_SECONDS}s",
        f"Entry delay: {ENTRY_DELAY_SECONDS}s",
        f"Holding period: {HOLD_SECONDS}s",
        f"Decision timestamps: {len(sampled):,}",
        f"Signals: {signal_count:,} ({100 * signal_count / len(sampled):.2f}% of decisions)",
        f"Valid simulated trades: {valid_trade_count:,}",
        f"Signals dropped for invalid entry/exit prices: {invalid_signal_count:,}",
        "",
        "Signal frequency by number of trades in feature bar:",
        activity.to_string(index=False, float_format=lambda x: f"{x:.4f}"),
        "",
        "Strategy return distribution and tail diagnostics:",
        tails.to_string(index=False, float_format=lambda x: f"{x:.6f}"),
        "",
        "Caveats:",
        "- Trade prices are proxies, not contemporaneous bid/ask midpoint prices or guaranteed fills.",
        "- Costs are shown as a break-even curve; they are not a verified fee schedule or execution model.",
        "- The June sample has seven days and is exploratory; do not interpret row-level observations as independent.",
        "- A top-tail share can exceed 100% because negative trades offset positive trades in total P&L.",
    ]
    (REPORT_DIR / "diagnostics_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    df = load_development_data()

    print(f"Loaded development data: {INPUT_PATH}")
    print(f"Rows: {len(df):,}; features/targets: validated")

    print("\n1/6 Building OFI bucket summaries and plot...")
    bucket_summary = make_bucket_summary(df)

    print("2/6 Building return distribution diagnostics...")
    distribution = make_return_distribution(df)
    print(distribution.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    print("3/6 Building daily mean-return chart...")
    daily_means = make_daily_means(df)

    print("4/6 Building the frozen-rule trade sample...")
    sampled, trades = build_development_strategy_trades(df)
    signal_rate = (sampled["direction"] != 0).mean() if len(sampled) else np.nan
    print(f"Decision timestamps: {len(sampled):,}")
    print(f"Signals: {int((sampled['direction'] != 0).sum()):,} ({signal_rate:.2%})")
    print(f"Valid simulated trades: {len(trades):,}")

    print("5/6 Measuring signal frequency by feature-bar trade count...")
    activity = make_activity_breakdown(sampled)
    print(activity.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("6/6 Measuring tails and plotting the cost curve...")
    tails = make_strategy_tail_statistics(trades)
    make_cost_curve(trades)
    print(tails.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    write_text_summary(df, distribution, sampled, trades, activity, tails)

    print("\nFinished. Outputs saved under:")
    print(f"  Tables and summary: {REPORT_DIR}")
    print(f"  Figures:            {FIGURE_DIR}")
    print("\nNo data was downloaded or accessed outside the June 1-7 development sample.")


if __name__ == "__main__":
    main()
