# BTCUSDT Order-Flow Imbalance Study

A small quantitative research project testing whether aggressive buy/sell volume imbalance predicts short-horizon BTCUSDT returns, and whether a simple strategy based on it survives transaction costs.

## Main conclusion

Order-flow imbalance showed positive associations with average future last-trade-price returns in the June–July 2025 sample. A fixed-threshold rule also produced a small positive gross average return in the later July evaluation (+0.072719 bps per trade). However, the estimated edge was smaller than even a hypothetical 0.1 bps round-trip cost, before realistic spread, fees and slippage. The strategy is **not shown to be economically viable**.

Read the full [research report](reports/final_report.md) for data, methodology, results and limitations.

## Research question

Does aggressive order-flow imbalance predict BTCUSDT spot returns over 1–30 seconds, and can a simple directional trading rule capture the relationship after costs?

## Method

1. Download Binance BTCUSDT spot aggregate trades.
2. Sign each trade's quantity using the aggressor side.
3. Aggregate to one-second bars and calculate normalized signed-volume imbalance.
4. Calculate forward last-trade-price returns.
5. Explore correlations and conditional returns.
6. Test a fixed rule: go long for imbalance ≥ +0.75, short for imbalance ≤ −0.75, otherwise stay flat. Sample every five seconds, wait one second before the entry-price proxy, and hold for five seconds.
7. Measure gross returns and show sensitivity to hypothetical round-trip costs.

## Key July evaluation results

- Trades: 364,634
- Mean gross return: +0.072719 bps per trade
- Gross win rate: 36.22%
- Days with positive mean gross returns: 31 / 31
- Break-even round-trip cost: about 0.072719 bps
- Mean net return at 1 bps cost: −0.927281 bps per trade

These are historical simulation results, not evidence of live or executable profitability.

## Limitations

- Uses last-trade-price proxies rather than historical bid–ask midpoint prices.
- Forward-fills the last price across seconds without trades, producing many zero returns at short horizons.
- Does not model spread, fees, slippage, market impact, latency, borrow/funding or actual order fills.
- Short positions are simplified and may require margin or other arrangements in spot markets.
- July correlation summaries were inspected before the July strategy backtest, so July is a later-period evaluation, not a completely blind preregistered holdout.
- Only June–July 2025 is studied; results may not generalize to other periods or market regimes.

## Project layout

```text
btc-flow-study/
├── data/
│   ├── raw/          # Downloaded daily archives (not committed)
│   └── processed/    # One-second bars and targets (not committed)
├── src/              # Download, processing, diagnostics and backtest scripts
├── reports/
│   ├── final_report.md
│   ├── backtest_trades_2025-07-01_to_2025-07-31.csv
│   └── backtest_daily_2025-07-01_to_2025-07-31.csv
├── requirements.txt
└── README.md
```

## Running the core scripts

Use a Python virtual environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Then run the relevant scripts from the project root. Date ranges are configured by constants at the top of the downloader, dataset builder and backtest scripts. Keep each date range's outputs separate so the development results and July evaluation are not accidentally overwritten.

## Data and reproducibility notes

The raw Binance archives should be downloaded separately and retained locally rather than committed to Git. Record the exact date range and configuration used for each run. The source scripts include exploratory diagnostics; the final report explains which outputs support the main claims.

## Responsible interpretation

This repository is an empirical research exercise, not a trading recommendation. The main result is that a small gross association did not leave a persuasive cost budget for a practical strategy under the assumptions tested.
