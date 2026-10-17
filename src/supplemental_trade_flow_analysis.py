from pathlib import Path
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]

JUNE_TARGETS = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "BTCUSDT-targets-2025-06-01_to_2025-06-07.csv"
)

SEPTEMBER_TRADES = (
    PROJECT_DIR
    / "reports"
    / "backtest_trades_2026-09-01_to_2026-09-30.csv"
)

REPORT_DIR = PROJECT_DIR / "reports"
FIGURE_DIR = REPORT_DIR / "figures"


def require_columns(df, columns, label):
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(
            f"{label} is missing columns: {sorted(missing)}"
        )


def trimmed_mean(values, proportion):
    """Remove the same proportion from each tail before averaging."""
    values = np.sort(np.asarray(values, dtype=float))
    cut = int(math.floor(proportion * len(values)))

    if len(values) - 2 * cut <= 0:
        return float("nan")

    return float(np.mean(values[cut:len(values) - cut]))


def analyse_june_buckets():
    if not JUNE_TARGETS.exists():
        raise FileNotFoundError(
            f"June targets not found: {JUNE_TARGETS}\n"
            "Check data/processed for the actual June target filename."
        )

    df = pd.read_csv(JUNE_TARGETS)

    require_columns(
        df,
        ["flow_imbalance", "future_return_1s_bps"],
        "June target dataset",
    )

    valid = df[
        ["flow_imbalance", "future_return_1s_bps"]
    ].copy()

    valid = valid.replace([np.inf, -np.inf], np.nan).dropna()

    if len(valid) < 100:
        raise ValueError(
            f"Too few valid June observations: {len(valid)}"
        )

    # Use quantile bins without splitting identical OFI values across
    # arbitrary boundaries. Tied quantiles may yield fewer than 10 bins.
    valid["ofi_bucket"] = pd.qcut(
        valid["flow_imbalance"],
        q=10,
        duplicates="drop",
    )

    target = "future_return_1s_bps"

    buckets = (
        valid.groupby("ofi_bucket", observed=True)
        .agg(
            observations=(target, "size"),
            ofi_min=("flow_imbalance", "min"),
            ofi_max=("flow_imbalance", "max"),
            mean_ofi=("flow_imbalance", "mean"),
            mean_future_return_bps=(target, "mean"),
            median_future_return_bps=(target, "median"),
            zero_return_pct=(
                target,
                lambda x: 100 * np.mean(x.to_numpy() == 0),
            ),
        )
        .reset_index()
    )

    buckets["ofi_bucket"] = buckets["ofi_bucket"].astype(str)

    bucket_path = REPORT_DIR / "ofi_return_buckets_june_2025.csv"
    buckets.to_csv(bucket_path, index=False)

    returns = valid[target].to_numpy(dtype=float)
    ofi = valid["flow_imbalance"].to_numpy(dtype=float)

    print("\nJUNE 1-7: OFI BUCKETS")
    print(f"Valid observations: {len(valid):,}")
    print(f"Pearson correlation: {np.corrcoef(ofi, returns)[0, 1]:.6f}")
    print(
        "Spearman correlation: "
        f"{valid['flow_imbalance'].corr(valid[target], method='spearman'):.6f}"
    )
    print(
        "Zero-return share: "
        f"{100 * np.mean(returns == 0):.2f}%"
    )
    print(buckets.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(f"Saved: {bucket_path}")

    # Plot mean future return by OFI quantile bucket.
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(
        buckets["ofi_bucket"],
        buckets["mean_future_return_bps"],
    )
    ax.axhline(0, linewidth=1)
    ax.set_title("Mean 1-Second Future Return by OFI Quantile")
    ax.set_xlabel("OFI quantile interval")
    ax.set_ylabel("Mean future return (bps)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()

    plot_path = FIGURE_DIR / "06_mean_future_return_by_ofi_bucket.png"
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)
    print(f"Saved: {plot_path}")


def analyse_september_tails():
    if not SEPTEMBER_TRADES.exists():
        raise FileNotFoundError(
            f"September trades not found: {SEPTEMBER_TRADES}"
        )

    trades = pd.read_csv(SEPTEMBER_TRADES)
    require_columns(
        trades,
        ["gross_return_bps"],
        "September trade dataset",
    )

    returns = pd.to_numeric(
        trades["gross_return_bps"],
        errors="coerce",
    ).dropna().to_numpy(dtype=float)

    returns = returns[np.isfinite(returns)]

    if len(returns) == 0:
        raise ValueError("No valid September trade returns found.")

    n = len(returns)
    ordered = np.sort(returns)
    total_return_sum = float(returns.sum())
    top_count = max(1, math.ceil(0.01 * n))
    bottom_count = top_count

    top_sum = float(ordered[-top_count:].sum())
    bottom_sum = float(ordered[:bottom_count].sum())

    def contribution_pct(value):
        if total_return_sum == 0:
            return float("nan")
        return 100 * value / total_return_sum

    summary = [
        ("Trade count", n, "trades"),
        ("Mean gross return", returns.mean(), "bps/trade"),
        ("Median gross return", np.median(returns), "bps/trade"),
        ("Gross win rate", 100 * np.mean(returns > 0), "%"),
        ("Exact zero-return share", 100 * np.mean(returns == 0), "%"),
        ("Mean positive return", returns[returns > 0].mean(), "bps"),
        ("Mean negative return", returns[returns < 0].mean(), "bps"),
        ("1% trimmed mean", trimmed_mean(returns, 0.01), "bps/trade"),
        ("5% trimmed mean", trimmed_mean(returns, 0.05), "bps/trade"),
        ("Top 1% trade count", top_count, "trades"),
        ("Top 1% summed gross return", top_sum, "sum of bps/trade"),
        ("Top 1% share of total gross-return sum",
         contribution_pct(top_sum), "%"),
        ("Bottom 1% trade count", bottom_count, "trades"),
        ("Bottom 1% summed gross return", bottom_sum, "sum of bps/trade"),
        ("Bottom 1% share of total gross-return sum",
         contribution_pct(bottom_sum), "%"),
        ("Mean net return at 1 bp cost",
         returns.mean() - 1, "bps/trade"),
        ("Mean net return at 15 bps cost",
         returns.mean() - 15, "bps/trade"),
        ("Mean net return at 20 bps cost",
         returns.mean() - 20, "bps/trade"),
    ]

    summary_df = pd.DataFrame(
        summary,
        columns=["metric", "value", "unit"],
    )

    summary_path = REPORT_DIR / "september_trade_tail_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    quantile_probs = [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]
    quantiles = pd.DataFrame({
        "quantile": [f"p{int(q * 100):02d}" for q in quantile_probs],
        "return_bps": np.quantile(returns, quantile_probs),
    })

    quantile_path = REPORT_DIR / "september_trade_return_quantiles.csv"
    quantiles.to_csv(quantile_path, index=False)

    print("\nSEPTEMBER 2026: TRADE-RETURN TAIL SUMMARY")
    print(summary_df.to_string(index=False))
    print("\nRETURN QUANTILES")
    print(quantiles.to_string(index=False))
    print(f"Saved: {summary_path}")
    print(f"Saved: {quantile_path}")

    # Show the central distribution while avoiding a few extreme returns
    # flattening the visual scale. Tail metrics remain based on all trades.
    low, high = np.quantile(returns, [0.005, 0.995])

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(returns, bins=100)
    ax.axvline(0, linewidth=1)
    ax.set_xlim(low, high)
    ax.set_title("September Gross Trade Returns (Central 99% Range)")
    ax.set_xlabel("Gross return (bps per trade)")
    ax.set_ylabel("Trade count")
    fig.tight_layout()

    plot_path = FIGURE_DIR / "07_september_trade_return_distribution.png"
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)
    print(f"Saved: {plot_path}")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    analyse_june_buckets()
    analyse_september_tails()


if __name__ == "__main__":
    main()