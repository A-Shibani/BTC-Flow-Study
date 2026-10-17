from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "BTCUSDT-targets-2025-06-01_to_2025-06-07.csv"
)

HORIZONS = (1, 5, 30)


def correlations(data, feature, target):
    """Return correlations on aligned, non-missing observations."""
    valid = data[[feature, target]].replace(
        [np.inf, -np.inf], np.nan
    ).dropna()

    if len(valid) < 2:
        return len(valid), np.nan, np.nan

    pearson = valid[feature].corr(valid[target], method="pearson")
    spearman = valid[feature].corr(valid[target], method="spearman")
    return len(valid), pearson, spearman


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Cannot find dataset: {DATA_PATH}")

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")

    feature = "flow_imbalance"

    # Recover the original bar date because feature timestamps are
    # shifted forward by one second to represent feature availability.
    bar_dates = (
        df.index - pd.Timedelta(seconds=1)
    ).strftime("%Y-%m-%d")

    print("=" * 72)
    print("RETURN DISTRIBUTION AND CORRELATION DIAGNOSTICS")
    print("=" * 72)

    for horizon in HORIZONS:
        target = f"future_return_{horizon}s_bps"

        valid = df[[feature, target]].replace(
            [np.inf, -np.inf], np.nan
        ).dropna()

        returns = valid[target]
        nonzero = valid.loc[returns != 0]

        print(f"\n--- Horizon: {horizon} second(s) ---")
        print(f"Valid observations: {len(valid):,}")
        print(f"Exactly zero returns: {(returns == 0).mean():.2%}")
        print(f"Positive returns:     {(returns > 0).mean():.2%}")
        print(f"Negative returns:     {(returns < 0).mean():.2%}")

        print(f"Mean return:           {returns.mean():.6f} bps")
        print(f"Median return:         {returns.median():.6f} bps")
        print(f"Mean positive move:    {returns[returns > 0].mean():.6f} bps")
        print(f"Mean negative move:    {returns[returns < 0].mean():.6f} bps")

        _, pearson, spearman = correlations(valid, feature, target)
        print(f"Pearson, all returns:  {pearson:.5f}")
        print(f"Spearman, all returns: {spearman:.5f}")

        if len(nonzero) >= 2:
            nonzero_spearman = nonzero[feature].corr(
                nonzero[target], method="spearman"
            )
            print(
                "Spearman, nonzero returns only: "
                f"{nonzero_spearman:.5f}"
            )
        else:
            print("Spearman on nonzero returns: insufficient data")

        # Diagnostic only: this checks whether larger absolute imbalances
        # tend to coincide with larger absolute future returns.
        magnitude_corr = valid[feature].abs().corr(
            returns.abs(), method="pearson"
        )
        print(
            "Corr(|imbalance|, |return|): "
            f"{magnitude_corr:.5f}"
        )

    print("\n" + "=" * 72)
    print("DAILY CORRELATIONS AND ZERO-RETURN SHARES")
    print("=" * 72)
    print(
        "Date       | Horizon | Observations | Zero returns | "
        "Pearson | Spearman"
    )

    for day in sorted(set(bar_dates)):
        day_mask = bar_dates == day

        for horizon in HORIZONS:
            target = f"future_return_{horizon}s_bps"

            valid = df.loc[
                day_mask, [feature, target]
            ].replace([np.inf, -np.inf], np.nan).dropna()

            if valid.empty:
                continue

            zero_share = (valid[target] == 0).mean()
            _, pearson, spearman = correlations(
                valid, feature, target
            )

            print(
                f"{day} | {horizon:>7}s | "
                f"{len(valid):>12,} | {zero_share:>12.2%} | "
                f"{pearson:>7.4f} | {spearman:>8.4f}"
            )


if __name__ == "__main__":
    main()
