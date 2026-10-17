

\# Research Design and Experiment Log



\## Research question



Does short-horizon order-flow imbalance predict future BTCUSDT

price movements, and does the observed relationship survive

realistic trading costs?



\## Primary strategy specification



\- Instrument: Binance BTCUSDT spot trade data.

\- Feature: one-second signed-volume order-flow imbalance.

\- Long signal: OFI >= 0.75.

\- Short signal: OFI <= -0.75.

\- Otherwise: no position.

\- Decision interval: every five seconds.

\- Entry delay: one second after signal availability.

\- Holding period: five seconds after the entry delay.

\- Entry/exit price proxy: forward-filled last-trade price.

\- Primary rule: no minimum trade-count filter.

\- Position sizing: equal notional per simulated trade.

\- Costs: round-trip fee sensitivity; spread and slippage are

&#x20; not measured by the current trade-only dataset.



\## Data periods



\### Development: 1-7 June 2025



Used for initial feature development, exploratory correlations,

bucket analysis, return-distribution diagnostics, regression

controls, strategy baselines, placebo tests, lag-decay tests,

activity-filter sensitivity and implementation checks.



\### Previously examined evaluation periods



\- 8-30 June 2025: correlations and subsequent strategy evaluation.

\- 1-31 July 2025: correlation results and strategy evaluation.



These periods are not treated as completely untouched holdouts.



\### Reserved final holdout



\- 1-30 September 2026, subject to archive availability.

\- No strategy parameters will be changed after examining results.

\- The primary evaluation will use the frozen original OFI rule.

\- Results will be reported regardless of whether performance is

&#x20; positive or negative.



\## Exploratory analysis already performed



\- Future-return horizons: 1, 5 and 30 seconds.

\- Pearson and Spearman correlations.

\- OFI bucket-level returns and direction frequencies.

\- Return clipping, trimmed means and winsorised means.

\- Contributions from the largest and smallest 1% of trades.

\- Daily mean returns and block-bootstrap uncertainty.

\- Regression controls: trailing returns, volatility, trade count

&#x20; and volume.

\- Naive previous-return-sign baseline.

\- Within-day shuffled-OFI and matched-frequency random placebos.

\- OFI lag analysis: 0, 1, 2, 5, 10 and 30 seconds.

\- Activity-filter sensitivity: minimum 0, 2, 5 and 10 trades.



The activity filters are exploratory sensitivity tests, not a

replacement for the primary frozen strategy.



\## Parameter-selection transparency



The current threshold and timing choices are fixed for the primary

evaluation. The available records do not establish a complete,

systematic search over every possible threshold, delay or holding

period. Do not claim a preregistered parameter search or invent

the number of variants considered.



Earlier evaluation periods were inspected before all later

diagnostics had been completed. September is reserved to provide

a cleaner final chronological evaluation.



\## Economic assumptions and limitations



\- Fee tables are sensitivity calculations, not simulated fills.

\- Maker execution, queue priority and passive fill probability

&#x20; have not been modelled.

\- Bid-ask spread is unavailable from the aggregate-trade dataset.

\- Short exposure may involve margin, borrowing or other costs.

\- Last-trade prices are not executable bid/ask quotes.

\- Overlapping returns and trades are not independent observations.

\- Results from this historical sample do not establish future

&#x20; profitability.



\## Final holdout protocol



1\. Freeze the source code and primary strategy parameters.

2\. Record the Git commit and tag the frozen version.

3\. Verify the September data source and archive availability.

4\. Run the frozen primary strategy on September once.

5\. Record all metrics, including negative results and limitations.

6\. Do not change parameters and rerun against the same holdout.
