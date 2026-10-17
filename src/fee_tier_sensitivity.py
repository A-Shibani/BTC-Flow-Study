"""Apply published Binance spot fee scenarios to June activity-filter results.

Input:  reports/activity_filter_sensitivity_june_2025.csv
Output: reports/fee_tier_sensitivity_june_2025.csv

Fee percentages are based on Binance's public spot fee schedule checked
2026-10-17. Rates can vary by account, pair, discount eligibility and date.
Maker fills are hypothetical scenarios: a limit order is not guaranteed to
execute as maker, and the current trade-price backtest does not model fills.
"""
from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
INPUT = PROJECT_DIR / "reports" / "activity_filter_sensitivity_june_2025.csv"
OUTPUT = PROJECT_DIR / "reports" / "fee_tier_sensitivity_june_2025.csv"

# Convert each side's published fee percentage into bps, then sum entry+exit.
# Source: https://www.binance.com/en/fee/trading (checked 2026-10-17)
SCENARIOS = [
    {
        "scenario": "Spot regular user, taker both sides",
        "entry_fee_bps": 10.0,
        "exit_fee_bps": 10.0,
        "execution_assumption": "Marketable/taker execution on entry and exit",
    },
    {
        "scenario": "Spot regular user, BNB-discounted taker both sides",
        "entry_fee_bps": 7.5,
        "exit_fee_bps": 7.5,
        "execution_assumption": "Assumes eligible 25% BNB fee discount on both sides",
    },
    {
        "scenario": "Spot VIP 9, maker both sides",
        "entry_fee_bps": 1.1,
        "exit_fee_bps": 1.1,
        "execution_assumption": "Hypothetical maker fills; VIP 9 qualification required",
    },
    {
        "scenario": "Spot VIP 9, maker + taker",
        "entry_fee_bps": 1.1,
        "exit_fee_bps": 2.3,
        "execution_assumption": "One maker fill and one taker fill; VIP 9 qualification required",
    },
    {
        "scenario": "Spot VIP 9, taker both sides",
        "entry_fee_bps": 2.3,
        "exit_fee_bps": 2.3,
        "execution_assumption": "Taker fills on both sides; VIP 9 qualification required",
    },
    {
        "scenario": "Spot VIP 9 with BNB discount, maker both sides",
        "entry_fee_bps": 0.825,
        "exit_fee_bps": 0.825,
        "execution_assumption": "Hypothetical maker fills plus eligible BNB discount; VIP 9 qualification required",
    },
    {
        "scenario": "Spot VIP 9 with BNB discount, maker + taker",
        "entry_fee_bps": 0.825,
        "exit_fee_bps": 1.725,
        "execution_assumption": "One maker and one taker fill plus eligible BNB discount; VIP 9 qualification required",
    },
    {
        "scenario": "Spot VIP 9 with BNB discount, taker both sides",
        "entry_fee_bps": 1.725,
        "exit_fee_bps": 1.725,
        "execution_assumption": "Taker fills both sides plus eligible BNB discount; VIP 9 qualification required",
    },
]


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Cannot find {INPUT}. Run src/activity_conditioned.py first."
        )

    filters = pd.read_csv(INPUT)
    required = {"min_trade_count_filter", "valid_trades", "mean_gross_bps"}
    missing = required - set(filters.columns)
    if missing:
        raise ValueError(f"Input is missing columns: {sorted(missing)}")

    rows = []
    for _, filter_row in filters.iterrows():
        for fee in SCENARIOS:
            round_trip = fee["entry_fee_bps"] + fee["exit_fee_bps"]
            rows.append({
                "min_trade_count_filter": int(filter_row["min_trade_count_filter"]),
                "valid_trades": int(filter_row["valid_trades"]),
                "mean_gross_bps": float(filter_row["mean_gross_bps"]),
                "fee_scenario": fee["scenario"],
                "entry_fee_bps": fee["entry_fee_bps"],
                "exit_fee_bps": fee["exit_fee_bps"],
                "round_trip_fee_bps": round_trip,
                "mean_net_bps_before_spread_slippage_and_borrow":
                    float(filter_row["mean_gross_bps"]) - round_trip,
                "execution_assumption": fee["execution_assumption"],
            })

    result = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)

    print("BINANCE SPOT FEE-TIER SENSITIVITY")
    print("Schedule checked: 2026-10-17")
    print("Source: https://www.binance.com/en/fee/trading")
    print("Net figures subtract entry + exit fees from gross mean return.")
    print("They still exclude spread, slippage, borrow/funding and missed fills.\n")

    display_cols = [
        "min_trade_count_filter", "valid_trades", "mean_gross_bps",
        "fee_scenario", "round_trip_fee_bps",
        "mean_net_bps_before_spread_slippage_and_borrow",
    ]
    print(result[display_cols].to_string(
        index=False,
        formatters={
            "mean_gross_bps": lambda x: f"{x:.5f}",
            "round_trip_fee_bps": lambda x: f"{x:.3f}",
            "mean_net_bps_before_spread_slippage_and_borrow": lambda x: f"{x:.5f}",
        },
    ))
    print(f"\nSaved: {OUTPUT}")
    print("Caution: VIP 9 is a very high eligibility tier; maker fills are not guaranteed.")


if __name__ == "__main__":
    main()
