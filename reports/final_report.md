# Does Crypto Order-Flow Imbalance Predict Short-Horizon Returns?

**Market:** Binance BTCUSDT spot
**Research period:** 1 June–31 July 2025
**Status:** Exploratory research with a later-period strategy evaluation

## Executive summary

This study investigates whether aggressive buy/sell volume imbalance in BTCUSDT trades is associated with short-horizon price changes, and whether a simple trading rule based on that imbalance could survive transaction costs.

Across the exploratory sample, the linear association between order-flow imbalance and future last-trade-price returns was consistently positive. A fixed-threshold strategy also produced a small positive average gross return during the later July period. However, the measured gross edge was only **0.07272 basis points per trade** in July, versus an illustrative round-trip cost of 1 basis point. Under that cost assumption, the mean return becomes **−0.92728 bps per trade**.

The principal conclusion is therefore:

> The data contains a repeatable gross association in this sample, but the tested trading rule does not appear economically viable under even modest cost assumptions. The evidence is not sufficient to claim a tradable edge.

The study is useful as a research exercise because it documents feature construction, temporal evaluation, target diagnostics, cost sensitivity, and limitations rather than treating a positive correlation as proof of profitability.

## Research question and hypothesis

**Question:** Does short-horizon order-flow imbalance predict subsequent BTCUSDT price movements, and does any predictive edge survive trading costs?

**Hypothesis:** When aggressive buying volume exceeds aggressive selling volume in a completed one-second interval, subsequent returns may be higher; when aggressive selling dominates, subsequent returns may be lower.

The hypothesis is evaluated using Binance spot aggregate trades. This dataset contains trades, not the contemporaneous best bid and ask, so the price measure used here is the last executed trade price rather than a bid–ask midpoint.

## Data and feature construction

### Data source and periods

Historical Binance BTCUSDT spot aggregate-trade archives were downloaded for:

- **1–7 June 2025:** initial exploration and diagnostics.
- **8–30 June 2025:** development-period analysis and initial strategy evaluation.
- **1–31 July 2025:** later-period strategy evaluation with fixed rules.

The July processing dataset contains 2,678,400 one-second rows, corresponding to 31 complete days. The July backtest sampled 535,680 decision timestamps at five-second intervals. Of 364,636 threshold signals, two lacked usable entry/exit price proxies, leaving 364,634 simulated trades.

### Order-flow imbalance

Each aggregate trade is signed according to the aggressor side:

- Positive quantity when the buyer is the aggressor (`buyer_is_maker` is false).
- Negative quantity when the seller is the aggressor (`buyer_is_maker` is true).

For second \(t\), the feature is:

\[
\mathrm{OFI}_t = \frac{\sum_i s_i q_i}{\sum_i q_i}
\]

where \(q_i\) is trade quantity and \(s_i\) is +1 for aggressive buys and −1 for aggressive sells. The feature ranges from −1 to +1 when volume is nonzero. Imbalance is missing in seconds with no traded volume.

### Price targets

Trades are aggregated into one-second bars. The price proxy is the last trade price within each second. For target construction, the last known trade price is carried forward across seconds without trades. Returns are measured in basis points:

\[
r_{t,h}^{\mathrm{bps}} = 10{,}000\left(\frac{P_{t+h}}{P_t}-1\right)
\]

The initial diagnostics examined horizons of 1, 5 and 30 seconds. The trading rule uses a one-second entry delay and a five-second holding period, sampling signals every five seconds.

## Exploratory findings

The pooled Pearson correlations from the initial June 1–7 sample were:

| Future horizon | Pearson correlation | Spearman correlation |
|---|---:|---:|
| 1 second | +0.0896 | −0.2392 |
| 5 seconds | +0.0971 | −0.0901 |
| 30 seconds | +0.0657 | +0.0485 |

For June 1–7, the pooled linear associations were positive at all three horizons, but Pearson and Spearman differed at short horizons. Approximately 49% of one-second returns in the broader seven-day exploratory sample were exactly zero. This is partly a consequence of using last trade prices and carrying prices forward over no-trade seconds. It complicates the interpretation of rank correlations and directional prediction.

The positive Pearson correlations were also observed across the 23 days of 8–30 June and the 31 days of July. These correlations are evidence of association in the data, not proof of a causal effect or profitable execution.

## Frozen strategy specification

The strategy specification used for the June 8–30 and July evaluations was:

- **Signal interval:** every five seconds, aligned to UTC timestamps whose second component is divisible by five.
- **Long signal:** OFI \(\geq +0.75\).
- **Short signal:** OFI \(\leq -0.75\).
- **Otherwise:** remain flat.
- **Entry delay:** one second after feature availability.
- **Holding period:** five seconds.
- **Price proxy:** last-trade-price series, forward-filled over no-trade seconds.

The long/short return is the underlying price return multiplied by +1 for a long and −1 for a short. This is a simplified directional simulation, not a faithful execution model. In particular, it does not model order-book spread, queue position, market impact, latency, funding/borrow, or the mechanics and costs of establishing short exposure in spot markets.

## Strategy results

### June 8–30, 2025: development-period evaluation

| Metric | Result |
|---|---:|
| Simulated trades | 271,399 |
| Mean gross return per trade | +0.08437 bps |
| Gross win rate | 37.29% |
| Long trades | 131,904 |
| Short trades | 139,495 |

These results were used to refine our understanding of the strategy and are not an independent test.

### July 1–31, 2025: later-period evaluation

| Metric | Result |
|---|---:|
| Simulated trades | 364,634 |
| Mean gross return per trade | +0.072719 bps |
| Median gross return per trade | 0.00000 bps |
| Gross win rate | 36.22% |
| Long trades | 176,996 |
| Short trades | 187,638 |
| Long mean gross return | +0.07447 bps |
| Short mean gross return | +0.07107 bps |
| Days with positive mean gross return | 31 / 31 |
| Lowest daily mean gross return | +0.019055 bps |
| Highest daily mean gross return | +0.122760 bps |
| Unweighted mean of daily gross means | +0.072600 bps |

The mean gross return was positive each day in July. The trade-weighted mean was +0.072719 bps, close to the unweighted mean of daily means (+0.072600 bps). The measured average gross edge in July was approximately 13.8% lower than the June 8–30 mean (+0.08437 bps).

### Uncertainty estimate

A circular moving-block bootstrap was applied to the 31 daily mean gross returns, rather than treating individual trades as independent observations. The reported 95% intervals for the mean daily gross return were:

| Resampled block length | 95% interval (bps) |
|---|---:|
| 1 day | [0.063398, 0.081854] |
| 3 days | [0.061098, 0.084034] |
| 5 days | [0.059647, 0.085608] |

These intervals describe uncertainty in the average of daily gross means under this resampling setup. They do not measure uncertainty in real executable net returns, account for all possible regime changes, or establish profitability after costs. There are only 31 daily observations, and a more complete inference procedure could be warranted in a future extension.

## Transaction-cost sensitivity

The July mean gross return of +0.072719 bps per trade is also the approximate break-even round-trip cost, before omitted execution effects. Illustrative constant-cost scenarios give:

| Assumed round-trip cost | Mean net return per trade |
|---:|---:|
| 0.000 bps | +0.072719 bps |
| 0.025 bps | +0.047719 bps |
| 0.050 bps | +0.022719 bps |
| 0.075 bps | −0.002281 bps |
| 0.100 bps | −0.027281 bps |
| 0.200 bps | −0.127281 bps |
| 1.000 bps | −0.927281 bps |

Even a hypothetical round-trip cost of 0.1 bps exceeds the estimated July gross edge. The simulation therefore offers little cost budget for spread, fees, slippage, latency, or market impact. The reported frictionless compounded equity return should not be presented as a realistic strategy return: it assumes the simulated trade-price returns can be captured and excludes material real-world frictions.

## Evaluation design and limitations

1. **Trade prices are not midpoint prices.** The last executed trade can be affected by bid–ask bounce and aggressor-side mechanics. Historical best bid/ask quotes were not included, so the study cannot isolate genuine midpoint movement from all trade-price effects.
2. **No-trade seconds introduce repeated prices.** Forward-filling the previous last trade price creates zero returns when no new trade changes the price. This helps explain the high share of zero short-horizon returns.
3. **July was a later-period evaluation, not a fully blind preregistered holdout.** The July daily and pooled correlations were printed and inspected during dataset processing before the strategy backtest was run. The strategy rules were not tuned after seeing July's strategy returns, but the period should not be described as completely untouched.
4. **Execution is simplified.** The model uses last-trade-price proxies rather than executable bid/ask quotes; assumes the short side can be implemented; and excludes actual fees, spread, slippage, market impact, borrow costs, funding, latency and rejected/partially filled orders.
5. **Costs are sensitivity assumptions.** The scenarios are not an assertion about a particular account's actual fee tier or execution conditions.
6. **Limited calendar coverage.** The study spans two months in 2025. It does not establish stability across other market regimes, assets, exchanges or periods.
7. **The strategy was deliberately not tuned to rescue performance.** Threshold searching after observing the results would increase data-snooping risk. Further strategy variations should be treated as new hypotheses and evaluated on newly reserved data.

## Conclusion

In this sample, one-second aggressive-volume imbalance was positively associated with subsequent average last-trade-price returns, and a fixed-threshold long/short rule showed small positive gross mean returns in June and July 2025. The July gross mean was +0.072719 bps per trade and positive daily means were observed on all 31 days. However, the break-even round-trip cost was only 0.072719 bps, leaving almost no room for actual trading frictions. A cost of 0.1 bps per round trip already makes the mean net return negative in this simplified calculation.

**The tested strategy should be regarded as economically unproven and likely unviable under realistic costs, not as a profitable trading system.** The main research contribution is a reproducible empirical workflow, careful separation of association from profitability, and a transparent account of where the data and backtest are insufficient.

## Reproducibility

The project scripts used during the study include the following (some are exploratory diagnostics rather than steps in the final pipeline):

- `src/download_range.py` — downloads daily Binance aggregate-trade archives.
- `src/build_multiday_dataset.py` — builds one-second bars and forward-return targets for a configured date range.
- `src/diagnose_signal.py`, `src/diagnose_targets.py`, `src/analyze_buckets.py` — exploratory feature/target diagnostics.
- `src/audit_sampling.py` — checks five-second decision sampling.
- `src/backtest.py` — implements the fixed threshold rule and cost sensitivity.
- `src/final_evaluation.py` — summarises July trade results and bootstraps daily means.

The scripts use date constants near the top of the file. To reproduce the reported analysis, use the archived CSV outputs and the same date configuration recorded in this report. Keep each evaluation period's trade and daily outputs under distinct filenames. The scripts' date constants determine the active range.

## September 2026 Historical Holdout

The frozen baseline (`v1.0-frozen-ofi`) was evaluated from
2026-09-01 through 2026-09-30. The signal thresholds and timing
parameters were unchanged. This is a retrospective historical holdout,
not a live forward test.

### Strategy specification

- Long when flow imbalance >= 0.75.
- Short when flow imbalance <= -0.75.
- Decision grid: every five seconds.
- Entry price proxy: t+1 second.
- Exit price proxy: t+6 seconds.
- Holding period: five seconds after entry.
- No minimum-trade-count filter.

### Results

- One-second observations: 2,592,000.
- Executed trades: 348,931.
- Long trades: 190,040; short trades: 158,891.
- Signals dropped because of unavailable prices: 1.
- Mean gross return: +0.09679 bps per trade.
- Median gross return: 0.00000 bps per trade.
- Gross win rate: 39.08%.
- Daily mean gross return was positive on 30 of 30 days.
- Lowest daily mean: +0.00371 bps.
- Highest daily mean: +0.16197 bps.

All 30 positive daily means are a descriptive observation, not proof of
statistical significance or future persistence. Daily and trade returns
may be dependent.

### Long versus short

| Side | Trades | Mean gross return | Gross win rate |
| --- | ---: | ---: | ---: |
| Long | 190,040 | 0.09097 bps | 38.995% |
| Short | 158,891 | 0.10375 bps | 39.173% |

### Uncertainty analysis

A moving-block bootstrap was applied to the 30 daily mean returns.
The unweighted mean of the 30 daily means was 0.095398 bps, distinct
from the trade-weighted overall mean of 0.096789 bps. The descriptive
95% bootstrap intervals for the unweighted mean of daily means were:

| Daily block length | 95% interval for unweighted mean of daily means |
| ---: | ---: |
| 1 day | [0.082076, 0.108033] bps |
| 3 days | [0.079751, 0.110677] bps |
| 5 days | [0.081453, 0.109780] bps |

All three intervals are above zero. This supports a positive average
gross return within this sample, but does not establish persistence in
future months. The resampling unit is the daily mean, not the individual
trade. With only 30 days, these intervals remain sensitive to the sample
and bootstrap assumptions; they are not proof of an executable edge.

### Transaction costs

The mean gross return implies a break-even round-trip cost of only
0.09679 bps per trade under this simplified return model, before other
omitted execution effects.

The existing cost-sensitivity calculation gives the following mean
returns after hypothetical round-trip costs:

| Round-trip cost | Mean net return |
| ---: | ---: |
| 0 bps | +0.09679 bps |
| 1 bp | -0.90321 bps |
| 2 bps | -1.90321 bps |

Binance's published Spot fee schedule, checked on 2026-10-17
(https://www.binance.com/en/fee/trading), lists standard fees of
0.10% per side and 0.075% per side when the displayed BNB discount
applies. These correspond to 20 bps and 15 bps round trip respectively.
At those rates, the modelled mean net returns would be -19.90321 bps
and -14.90321 bps per trade.

Even the published VIP 9 maker rate of 0.011% per side would correspond
to 2.2 bps round trip if both executions qualified as maker fills.
With the displayed BNB discount, that would be 1.65 bps round trip.
Both exceed the observed gross edge. VIP eligibility, fee discounts,
pair-specific promotions and actual account fees must not be assumed.

The strategy therefore does not survive the assessed Spot fee scenarios.
These calculations do not include spread, slippage, queue position,
market impact or execution uncertainty.

### Limitations and conclusion

The backtest uses last-trade-price proxies, not executable bid/ask
quotes, and does not model whether simulated fills would occur. The
short side also requires an appropriate shorting product or venue and
its own fee and execution assumptions.

The frozen rule produced a small positive average gross return in this
historical holdout, but the tested implementation is not economically
viable under the assessed transaction costs. The result does not
establish an executable trading edge. A possible future research
direction is to test whether order-flow imbalance adds value to
market-making or quote-skew decisions; that would require a separate,
execution-aware model and independent evaluation.

The fee-free compounded result is omitted as a performance claim
because this backtest does not establish a realistic capital allocation
or executable reinvestment model.
