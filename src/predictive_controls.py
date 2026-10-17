"""Regression controls and a naive lagged-return baseline for BTCUSDT OFI.

Uses only the June 1-7 development dataset. It does not read or modify the
later-period evaluation data. Requires pandas and numpy only.

The regression keeps the regular one-second time grid. On seconds with no
trades, OFI is set to zero for the regression only, while log trade count and
log volume are included as activity controls. Strategy signals still require
an observed OFI value.
"""

from pathlib import Path
import math

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "BTCUSDT-targets-2025-06-01_to_2025-06-07.csv"
)
REPORT_DIR = PROJECT_DIR / "reports"
HORIZONS = (1, 5, 30)
SIGNAL_INTERVAL_SECONDS = 5
ENTRY_DELAY_SECONDS = 1
HOLD_SECONDS = 5
LONG_THRESHOLD = 0.75
SHORT_THRESHOLD = -0.75


CONTROL_COLS = [
    "past_return_1s_bps",
    "past_return_5s_bps",
    "volatility_30s_bps",
    "log_trade_count",
    "log_volume_btc",
]


def load_and_engineer() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Development dataset not found: {DATA_PATH}\n"
            "Expected BTCUSDT-targets-2025-06-01_to_2025-06-07.csv."
        )

    df = pd.read_csv(
        DATA_PATH,
        parse_dates=["feature_available_at_utc"],
    ).set_index("feature_available_at_utc")

    required = {
        "flow_imbalance", "close_price", "trade_count", "total_qty_btc",
        "future_return_1s_bps", "future_return_5s_bps",
        "future_return_30s_bps",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {sorted(missing)}")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("Timestamps must be unique and chronologically sorted.")
    if len(df) > 1:
        gaps = df.index.to_series().diff().dropna()
        if not (gaps == pd.Timedelta(seconds=1)).all():
            raise ValueError("Dataset does not have a continuous one-second grid.")

    mark = df["close_price"].ffill()
    df["past_return_1s_bps"] = (mark / mark.shift(1) - 1.0) * 10_000
    df["past_return_5s_bps"] = (mark / mark.shift(5) - 1.0) * 10_000
    df["volatility_30s_bps"] = (
        df["past_return_1s_bps"].rolling(30, min_periods=30).std()
    )

    counts = pd.to_numeric(df["trade_count"], errors="coerce").fillna(0)
    volume = pd.to_numeric(df["total_qty_btc"], errors="coerce").fillna(0.0)
    df["log_trade_count"] = np.log1p(counts.clip(lower=0))
    df["log_volume_btc"] = np.log1p(volume.clip(lower=0))

    # For regression only, zero means no signed flow in an inactive bar.
    # Activity controls keep these bars distinguishable from low-volume bars.
    df["ofi_regression"] = pd.to_numeric(
        df["flow_imbalance"], errors="coerce"
    ).fillna(0.0)

    return df


def fit_ols(x: np.ndarray, y: np.ndarray):
    """Fit OLS and return coefficients, R-squared, residuals and design matrix."""
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ beta
    centered = y - y.mean()
    total_sum_squares = float(centered @ centered)
    residual_sum_squares = float(residuals @ residuals)
    r_squared = (
        1.0 - residual_sum_squares / total_sum_squares
        if total_sum_squares > 0
        else np.nan
    )
    return beta, r_squared, residuals


def hac_standard_errors(x: np.ndarray, residuals: np.ndarray, max_lags: int):
    """Newey-West HAC standard errors for OLS coefficients.

    Rows are kept on a regular one-second grid. max_lags is at least the
    forecast horizon, so overlapping forward-return targets are accounted for.
    """
    n, k = x.shape
    scores = x * residuals[:, None]
    meat = scores.T @ scores

    for lag in range(1, min(max_lags, n - 1) + 1):
        weight = 1.0 - lag / (max_lags + 1.0)
        cross = scores[lag:].T @ scores[:-lag]
        meat += weight * (cross + cross.T)

    bread = np.linalg.pinv(x.T @ x)
    covariance = bread @ meat @ bread
    # Small numerical negatives on the diagonal can occur through roundoff.
    variances = np.maximum(np.diag(covariance), 0.0)
    return np.sqrt(variances)


def design_matrix(data: pd.DataFrame, columns: list[str]) -> np.ndarray:
    values = data[columns].to_numpy(dtype=float)
    return np.column_stack([np.ones(len(data)), values])


def run_regressions(df: pd.DataFrame) -> pd.DataFrame:
    results = []
    predictor_sets = {
        "OFI only": ["ofi_regression"],
        "Controls only": CONTROL_COLS,
        "OFI + controls": ["ofi_regression", *CONTROL_COLS],
    }

    print("\n" + "=" * 82)
    print("PREDICTIVE REGRESSIONS — JUNE 1-7 DEVELOPMENT DATA")
    print("=" * 82)
    print(
        "Controls: trailing 1s/5s returns, trailing 30s volatility, "
        "log trade count and log BTC volume."
    )
    print(
        "Inactive bars have OFI=0 for regression only; activity controls remain. "
        "HAC standard errors use Newey-West with lags matched to the horizon."
    )

    for horizon in HORIZONS:
        target = f"future_return_{horizon}s_bps"
        columns = ["ofi_regression", *CONTROL_COLS, target]
        data = df[columns].replace([np.inf, -np.inf], np.nan).dropna()
        y = data[target].to_numpy(dtype=float)

        model_results = {}
        for model_name, predictors in predictor_sets.items():
            x = design_matrix(data, predictors)
            beta, r2, residuals = fit_ols(x, y)
            model_results[model_name] = (x, beta, r2, residuals, predictors)

            ofi_coef = np.nan
            ofi_hac_se = np.nan
            ofi_z = np.nan
            ofi_p = np.nan

            if model_name == "OFI + controls":
                hac_se = hac_standard_errors(x, residuals, max_lags=horizon)
                ofi_idx = 1 + predictors.index("ofi_regression")
                ofi_coef = float(beta[ofi_idx])
                ofi_hac_se = float(hac_se[ofi_idx])
                if ofi_hac_se > 0:
                    ofi_z = ofi_coef / ofi_hac_se
                    ofi_p = math.erfc(abs(ofi_z) / math.sqrt(2.0))

            row = {
                "horizon_seconds": horizon,
                "model": model_name,
                "observations": len(data),
                "r_squared": r2,
                "ofi_coefficient_bps_per_unit": ofi_coef,
                "ofi_hac_standard_error": ofi_hac_se,
                "ofi_hac_z_approx": ofi_z,
                "ofi_two_sided_p_approx": ofi_p,
                "hac_max_lags": horizon if model_name == "OFI + controls" else np.nan,
            }
            results.append(row)

        simple_r2 = model_results["OFI only"][2]
        control_r2 = model_results["Controls only"][2]
        full_r2 = model_results["OFI + controls"][2]
        print(f"\n{horizon}-second future return (bps), n={len(data):,}")
        print(f"  OFI-only R-squared:       {simple_r2:.8f}")
        print(f"  Controls-only R-squared:  {control_r2:.8f}")
        print(f"  OFI + controls R-squared: {full_r2:.8f}")
        full = results[-1]
        print(
            "  OFI coefficient after controls: "
            f"{full['ofi_coefficient_bps_per_unit']:.6f} bps per OFI unit"
        )
        print(
            "  HAC standard error / z / approximate p: "
            f"{full['ofi_hac_standard_error']:.6f} / "
            f"{full['ofi_hac_z_approx']:.3f} / "
            f"{full['ofi_two_sided_p_approx']:.3g}"
        )

    report = pd.DataFrame(results)
    return report


def strategy_summary(df: pd.DataFrame, direction: pd.Series, name: str) -> dict:
    mark = df["close_price"].ffill()
    entry = mark.shift(-ENTRY_DELAY_SECONDS)
    exit_price = mark.shift(-(ENTRY_DELAY_SECONDS + HOLD_SECONDS))

    decision_mask = df.index.second % SIGNAL_INTERVAL_SECONDS == 0
    direction = direction.reindex(df.index).fillna(0).astype(int)
    selected = pd.DataFrame(
        {
            "direction": direction.loc[decision_mask],
            "entry": entry.loc[decision_mask],
            "exit": exit_price.loc[decision_mask],
        },
        index=df.index[decision_mask],
    )
    selected = selected[selected["direction"] != 0].copy()
    selected = selected[
        selected["entry"].notna()
        & selected["exit"].notna()
        & (selected["entry"] > 0)
        & (selected["exit"] > 0)
    ]

    if selected.empty:
        gross = pd.Series(dtype=float)
    else:
        underlying = selected["exit"] / selected["entry"] - 1.0
        gross = selected["direction"] * underlying * 10_000

    return {
        "strategy": name,
        "decision_timestamps": int(decision_mask.sum()),
        "valid_trades": int(len(gross)),
        "signal_rate_pct": 100.0 * len(selected) / int(decision_mask.sum()),
        "mean_gross_bps": float(gross.mean()) if len(gross) else np.nan,
        "median_gross_bps": float(gross.median()) if len(gross) else np.nan,
        "gross_win_rate_pct": 100.0 * float((gross > 0).mean()) if len(gross) else np.nan,
        "net_mean_at_0_1bps": float(gross.mean() - 0.1) if len(gross) else np.nan,
        "net_mean_at_1bps": float(gross.mean() - 1.0) if len(gross) else np.nan,
        "net_mean_at_2bps": float(gross.mean() - 2.0) if len(gross) else np.nan,
    }


def compare_trading_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """Compare the frozen OFI rule with a simple last-second momentum rule."""
    ofi = df["flow_imbalance"]
    ofi_direction = pd.Series(
        np.select(
            [ofi >= LONG_THRESHOLD, ofi <= SHORT_THRESHOLD],
            [1, -1],
            default=0,
        ),
        index=df.index,
    )

    past_return = df["past_return_1s_bps"]
    momentum_direction = pd.Series(
        np.where(past_return > 0, 1, np.where(past_return < 0, -1, 0)),
        index=df.index,
    )

    summaries = [
        strategy_summary(df, ofi_direction, "Frozen OFI threshold rule"),
        strategy_summary(df, momentum_direction, "Naive previous-1s return sign"),
    ]
    summary = pd.DataFrame(summaries)

    print("\n" + "=" * 82)
    print("SIMPLE STRATEGY BASELINE COMPARISON — DEVELOPMENT DATA ONLY")
    print("=" * 82)
    print(
        "Both use the same 5-second decision grid, 1-second entry delay, "
        "and 5-second holding period. The momentum baseline is active only "
        "when the previous 1-second return is nonzero."
    )
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.5f}"))
    return summary


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_and_engineer()

    print(f"Loaded development data: {DATA_PATH}")
    print(f"Rows: {len(df):,}")
    print("Date range: June 1-7, 2025 (development data only)")

    regression_results = run_regressions(df)
    regression_path = REPORT_DIR / "predictive_controls_regression.csv"
    regression_results.to_csv(regression_path, index=False)

    baseline_results = compare_trading_baselines(df)
    baseline_path = REPORT_DIR / "development_strategy_baselines.csv"
    baseline_results.to_csv(baseline_path, index=False)

    print("\nSaved outputs:")
    print(f"  {regression_path}")
    print(f"  {baseline_path}")
    print("\nInterpretation caution: a small p-value is not proof of a tradable edge.")
    print("The approximate p-values use a normal reference for HAC z-statistics;")
    print("R-squared changes and effect sizes matter as well as significance.")


if __name__ == "__main__":
    main()
