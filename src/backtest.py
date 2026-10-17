from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# Frozen strategy configuration
# --------------------------------------------------

START_DATE = "2026-09-01"
END_DATE = "2026-09-30"

LONG_THRESHOLD = 0.75
SHORT_THRESHOLD = -0.75

SIGNAL_INTERVAL_SECONDS = 5
ENTRY_DELAY_SECONDS = 1
HOLD_SECONDS = 5

# Illustrative all-in round-trip costs, in basis points.
# These are sensitivity scenarios, not claims about actual fees.
COST_SCENARIOS_BPS = [0, 1, 2, 5, 10, 20]

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / f"BTCUSDT-targets-{START_DATE}_to_{END_DATE}.csv"
)
OUTPUT_DIR = PROJECT_DIR / "reports"


def load_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")

    if not df.index.is_monotonic_increasing:
        raise ValueError("Timestamps are not sorted.")

    if df.index.has_duplicates:
        raise ValueError("Duplicate timestamps found.")

    if len(df) > 1:
        gaps = df.index.to_series().diff().dropna()
        if not (gaps == pd.Timedelta(seconds=1)).all():
            raise ValueError(
                "Expected continuous one-second rows. "
                "Check the input dataset before backtesting."
            )

    required = {"flow_imbalance", "close_price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    return df


def build_trades(df):
    # Forward-fill only past known prices through no-trade seconds.
    # These are last-trade-price proxies, not executable bid/ask quotes.
    mark_price = df["close_price"].ffill()

    # Features at time t use the completed preceding one-second bar.
    # Entry is proxied at t+1; exit is proxied at t+6:
    # a one-second delay followed by five seconds of holding.
    entry_price = mark_price.shift(-ENTRY_DELAY_SECONDS)
    exit_price = mark_price.shift(
        -(ENTRY_DELAY_SECONDS + HOLD_SECONDS)
    )

    # Sample on UTC timestamps aligned to multiples of five seconds.
    sample_mask = (
    df.index.second % SIGNAL_INTERVAL_SECONDS == 0
    )

    sampled = pd.DataFrame(index=df.index[sample_mask])
    sampled["imbalance"] = df.loc[
        sample_mask, "flow_imbalance"
    ]
    sampled["entry_price"] = entry_price.loc[sampled.index]
    sampled["exit_price"] = exit_price.loc[sampled.index]

    sampled["direction"] = np.select(
        [
            sampled["imbalance"] >= LONG_THRESHOLD,
            sampled["imbalance"] <= SHORT_THRESHOLD,
        ],
        [1, -1],
        default=0,
    )

    directional = sampled[sampled["direction"] != 0].copy()

    valid_prices = (
        directional["entry_price"].notna()
        & directional["exit_price"].notna()
        & (directional["entry_price"] > 0)
        & (directional["exit_price"] > 0)
    )

    dropped = int((~valid_prices).sum())
    trades = directional.loc[valid_prices].copy()

    # Long returns follow the underlying return; short returns reverse it.
    underlying_return = (
        trades["exit_price"] / trades["entry_price"] - 1
    )
    trades["gross_return_bps"] = (
        trades["direction"] * underlying_return * 10_000
    )

    trades["side"] = np.where(
        trades["direction"] == 1, "LONG", "SHORT"
    )
    trades["date"] = trades.index.strftime("%Y-%m-%d")

    return sampled, trades, dropped


def compounded_return(return_bps):
    factors = 1 + np.asarray(return_bps, dtype=float) / 10_000

    if len(factors) == 0:
        return 0.0

    if np.any(factors <= 0):
        return -1.0

    return float(np.prod(factors) - 1)


def max_drawdown(return_bps):
    factors = 1 + np.asarray(return_bps, dtype=float) / 10_000

    if len(factors) == 0:
        return 0.0

    equity = np.cumprod(factors)
    equity_with_initial = np.concatenate(([1.0], equity))
    peaks = np.maximum.accumulate(equity_with_initial)
    drawdowns = equity_with_initial / peaks - 1

    return float(drawdowns.min())


def print_summary(trades):
    print("\n" + "=" * 76)
    print("BACKTEST SUMMARY")
    print("=" * 76)

    print(f"Data period: {START_DATE} to {END_DATE}")
    print(f"Long threshold:  >= {LONG_THRESHOLD}")
    print(f"Short threshold: <= {SHORT_THRESHOLD}")
    print(f"Signal interval: {SIGNAL_INTERVAL_SECONDS} seconds")
    print(f"Entry delay: {ENTRY_DELAY_SECONDS} second")
    print(f"Holding period: {HOLD_SECONDS} seconds")
    print(f"Executed trades: {len(trades):,}")

    if trades.empty:
        print("No trades could be executed. Check prices and signals.")
        return

    long_count = int((trades["direction"] == 1).sum())
    short_count = int((trades["direction"] == -1).sum())
    gross = trades["gross_return_bps"]

    print(f"Long trades: {long_count:,}")
    print(f"Short trades: {short_count:,}")
    print(f"Mean gross return per trade: {gross.mean():.5f} bps")
    print(f"Median gross return per trade: {gross.median():.5f} bps")
    print(f"Gross win rate: {(gross > 0).mean():.2%}")
    print(
        "Break-even round-trip cost before other omitted effects: "
        f"{gross.mean():.5f} bps per trade"
    )

    print("\nCOST SENSITIVITY")
    print(
        "Cost bps | Mean net bps | Net win rate | "
        "Compounded return | Max drawdown"
    )

    for cost in COST_SCENARIOS_BPS:
        net = gross - cost

        total_return = compounded_return(net)
        drawdown = max_drawdown(net)
        win_rate = (net > 0).mean()

        print(
            f"{cost:>8.2f} | "
            f"{net.mean():>12.5f} | "
            f"{win_rate:>12.2%} | "
            f"{total_return:>16.2%} | "
            f"{drawdown:>12.2%}"
        )


def build_daily_report(trades):
    if trades.empty:
        return pd.DataFrame()

    daily = trades.groupby("date").agg(
        trades=("gross_return_bps", "size"),
        long_trades=("direction", lambda x: int((x == 1).sum())),
        short_trades=("direction", lambda x: int((x == -1).sum())),
        mean_gross_bps=("gross_return_bps", "mean"),
        gross_win_rate=(
            "gross_return_bps",
            lambda x: (x > 0).mean(),
        ),
    )

    for cost in [0, 2, 5, 10, 20]:
        daily_net = trades["gross_return_bps"] - cost

        daily_return = (
            (1 + daily_net / 10_000)
            .groupby(trades["date"])
            .prod()
            - 1
        )

        daily[f"net_return_cost_{cost}bps_pct"] = (
            daily_return * 100
        )

    return daily


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data()
    sampled, trades, dropped = build_trades(df)

    print(f"One-second rows loaded: {len(df):,}")
    print(f"Decision timestamps sampled: {len(sampled):,}")
    print(
        "Signals meeting the threshold before price checks: "
        f"{int((sampled['direction'] != 0).sum()):,}"
    )
    print(f"Signals dropped due to unavailable prices: {dropped:,}")

    print_summary(trades)

    trades_path = OUTPUT_DIR / (
    f"backtest_trades_{START_DATE}_to_{END_DATE}.csv"
    )
    trades.to_csv(trades_path, index_label="signal_time_utc")

    daily = build_daily_report(trades)
    daily_path = OUTPUT_DIR / (
    f"backtest_daily_{START_DATE}_to_{END_DATE}.csv"
    )
    daily.to_csv(daily_path, index_label="date")

    if not daily.empty:
        print("\nDAILY PERFORMANCE")
        print(daily.to_string(float_format=lambda x: f"{x:.4f}"))

    print(f"\nTrade-level results saved to: {trades_path}")
    print(f"Daily results saved to: {daily_path}")


if __name__ == "__main__":
    main()
