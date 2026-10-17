# Frozen OFI Baseline Strategy

Freeze date: 2026-10-17
Reserved evaluation period: 2026-09-01 to 2026-09-30
Instrument: Binance BTCUSDT Spot aggregated trades

## Signal rules
- Long when flow_imbalance >= 0.75.
- Short when flow_imbalance <= -0.75.
- Otherwise, do not trade.
- No minimum-trade-count filter.

## Timing
- Decision grid: every 5 seconds.
- Entry price proxy: t + 1 second.
- Exit price proxy: t + 6 seconds.
- Holding period: 5 seconds after entry.

## Evaluation rules
- Keep all parameters unchanged for the September holdout.
- Report gross results separately from trading costs.
- Trade-price proxies are not guaranteed executable bid/ask prices.
- Spread, slippage, queue position and execution uncertainty are not
  modelled by this backtest.
- Do not interpret a positive gross return as proof of profitability.

This document freezes the current baseline for evaluation. It does
not claim the strategy is profitable or executable.
