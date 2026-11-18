# Does Crypto Order-Flow Imbalance Predict Short-Horizon Returns?

**Market:** Binance BTCUSDT Spot
**Research periods:** 1 June–31 July 2025, plus a reserved historical holdout of 1–30 September 2026
**Strategy version:** `v1.0-frozen-ofi`
**Status:** Historical empirical research; not a live forward test

## Executive summary

This study tests whether aggressive buy/sell volume imbalance in BTCUSDT aggregate trades is associated with short-horizon returns, then evaluates a simple directional rule and its sensitivity to transaction costs.

The initial June 2025 exploration found positive Pearson associations between order-flow imbalance (OFI) and future last-trade-price returns. A fixed-threshold strategy produced small positive mean gross returns in the June development evaluation, the July later-period evaluation, and the September 2026 historical holdout. The September holdout produced a trade-weighted mean gross return of **0.096789 basis points (bps) per trade** across 348,931 simulated trades.

That gross edge is extremely small. It implies a break-even round-trip cost of approximately **0.096789 bps per trade** under the simplified return model, before spread, slippage, market impact, queue position, latency and fill uncertainty. Binance's published regular Spot fee schedule lists 0.10% per side (20 bps round trip), or 0.075% per side (15 bps round trip) when the displayed BNB discount applies. Even the displayed VIP 9 maker rate with the BNB discount would be 1.65 bps round trip if both fills qualified as maker executions. These fee examples are far larger than the measured edge.

**Conclusion:** The strategy shows a small positive gross-return association in the tested historical samples, but the implementation is **not economically viable under the assessed fee scenarios**. The backtest uses last-trade-price proxies rather than executable bid/ask quotes and therefore does not establish an executable trading edge.

The contribution of the project is its research workflow: constructing features from raw trade archives, separating development and holdout periods, checking timing, running statistical and placebo diagnostics, testing cost sensitivity, and documenting a negative economic conclusion rather than treating a positive gross return as proof of profitability.

## 1. Research question and hypothesis

**Question:** Does short-horizon order-flow imbalance predict subsequent BTCUSDT price movements, and does a simple directional rule capture enough of that relationship to remain profitable after trading costs?

**Hypothesis:** When aggressive buying volume dominates a completed one-second interval, subsequent returns may be higher; when aggressive selling dominates, subsequent returns may be lower.

**Feature definition.** In this study, OFI denotes normalised
aggressor-signed trade-volume imbalance, calculated from executed
BTCUSDT aggregate trades. It is a trade-based proxy for directional
order flow, not the order-book-event OFI constructed from changes
in best-bid and best-ask depth. The feature is defined explicitly
in the methodology below.

The source data contains aggregate trades, not historical contemporaneous best bid and ask quotes. Price targets therefore use last-trade prices rather than midpoint returns. This distinction matters because last-trade prices can reflect bid–ask bounce and repeated prices in inactive seconds.

## 2. Data and feature construction

### 2.1 Data periods

Binance BTCUSDT Spot daily aggregate-trade archives were downloaded and converted to one-second bars for the following periods:

| Period | Purpose | Notes |
|---|---|---|
| 1–7 June 2025 | Initial exploration and diagnostics | Used to inspect OFI, returns, activity filters, placebo tests and model controls. |
| 8–30 June 2025 | Development-period strategy evaluation | Used for development and diagnostic analysis; not an independent holdout. |
| 1–31 July 2025 | Later-period strategy evaluation | Fixed rule evaluated on a later month, but not a fully blind preregistered holdout because July correlations had already been inspected. |
| 1–30 September 2026 | Reserved historical holdout | The baseline was tagged before running this evaluation. September is historical data, not a live forward test. |

### 2.2 Aggressor-signed volume and OFI

Each aggregate trade is signed using the `buyer_is_maker` field:

- Positive quantity when the buyer is the aggressor (`buyer_is_maker` is false).
- Negative quantity when the seller is the aggressor (`buyer_is_maker` is true).

For one-second interval \(t\), normalized order-flow imbalance is

\[
\mathrm{OFI}_t = \frac{\sum_i s_i q_i}{\sum_i q_i},
\]

where \(q_i\) is trade quantity and \(s_i\) is +1 for aggressive buys and −1 for aggressive sells. When volume is nonzero, OFI lies between −1 and +1. OFI is missing in seconds with no traded volume.

### 2.3 Price targets and time alignment

Trades are aggregated into one-second bars. The price proxy is the last trade price within each second. For target construction, the last known trade price is carried forward across seconds without trades. Forward returns are expressed in basis points:

\[
r_{t,h}^{\mathrm{bps}} = 10{,}000\left(\frac{P_{t+h}}{P_t}-1\right).
\]

Initial diagnostics examined 1-, 5- and 30-second horizons. The strategy samples on a five-second UTC grid, uses a one-second entry delay, and holds for five seconds after entry. The price index is shifted so a completed one-second feature is not treated as available before its interval ends.

## 3. Exploratory results

In the pooled 1–7 June 2025 exploratory dataset, the following correlation estimates were reported:

| Future horizon | Pearson correlation | Spearman correlation |
|---|---:|---:|
| 1 second | +0.0961 | −0.1793 |
| 5 seconds | +0.0921 | −0.0418 |
| 30 seconds | +0.0548 | +0.0458 |

Pearson and Spearman differ at short horizons. Approximately 49% of one-second returns in the broader seven-day exploratory sample were exactly zero. Carrying the last trade price forward across no-trade seconds contributes to this mass at zero and complicates the interpretation of rank correlations and directional prediction.

Regression diagnostics on the June 1–7 development sample included trailing returns, trailing volatility, log trade count and log volume as controls, with HAC/Newey–West standard errors. OFI coefficients remained positive for the 1-, 5- and 30-second future-return regressions, but the associated explanatory power was small. Statistical significance in these specifications does not establish causal predictability or an economically tradable strategy; it must be interpreted alongside dependence, specification choices and execution costs.

Additional development diagnostics found that filtering for more active seconds increased the observed gross average return but substantially reduced the trade count. For example, the primary no-activity-filter diagnostic had 80,688 trades and a mean gross return of 0.07485 bps; requiring at least five trades in the signal second reduced the sample to 25,624 trades and increased the mean to 0.19983 bps. These were exploratory sensitivity analyses, not parameters adopted in the frozen strategy. They must not be interpreted as a new strategy validated on the September holdout.

Lag diagnostics showed that the average gross result declined as the OFI signal was lagged: approximately 0.07485 bps at lag 0, 0.05803 at lag 1, 0.02171 at lag 5, and 0.00393 at lag 30. Shuffled-OFI and random-time placebo checks placed the observed development-period result above the simulated placebo distributions in the tested setup. These checks help investigate timing and association, but they do not model executable fills, remove all data-mining concerns, or establish profitability after costs.


### 3.1 Additional predictive diagnostics: June 1-7, 2025

These are development-sample diagnostics. They are not independent
holdout results and do not establish net profitability.

#### Regression controls

Models compare OFI-only, controls-only, and combined predictions of
future last-trade-price returns. Controls include trailing 1-second
and 5-second returns, trailing 30-second volatility, log trade count,
and log BTC volume. Inactive bars use OFI = 0 for this regression.
The combined model uses HAC/Newey-West standard errors.

| Horizon | OFI coefficient (bps per OFI unit) | HAC SE | HAC t-statistic | OFI-only R-squared | Controls-only R-squared | Combined R-squared |
|---:|---:|---:|---:|---:|---:|---:|
| 1 second | 0.030314 | 0.000673 | 45.028 | 0.008949 | 0.020244 | 0.023734 |
| 5 seconds | 0.079068 | 0.001947 | 40.620 | 0.008191 | 0.017241 | 0.020829 |
| 30 seconds | 0.138052 | 0.006866 | 20.107 | 0.002875 | 0.005099 | 0.006566 |

The combined model's R-squared exceeds the controls-only R-squared at each horizon,
but the absolute explanatory power remains small. Large t-statistics
do not establish economic significance or causality, and inference
depends on the HAC specification and treatment of serial dependence.

The initial 1-second Spearman correlation was negative even though
Pearson correlation and the regression coefficient were positive.
These statistics measure different aspects of a relationship. Zero
returns, ties, nonlinear conditional means, and bid-ask bounce are
possible explanations, not established causes. The return distribution
and conditional means by OFI bucket should be examined directly.

#### Placebo checks

Each placebo procedure used 500 repetitions on the June 1-7 development
sample. The observed mean gross return was 0.074850 bps per trade.

| Placebo procedure | Repetitions | Null mean (bps) | Null SD (bps) | 5th percentile | Median | 95th percentile | Empirical upper-tail p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Shuffle OFI within each day | 500 | -0.000228 | 0.003758 | -0.006444 | -0.000145 | 0.005944 | 0.001996 |
| Random times matched on daily trade and side counts | 500 | -0.000677 | 0.003769 | -0.006827 | -0.000373 | 0.005488 | 0.001996 |

The observed mean exceeded the 95th percentile of both placebo
distributions. With 500 repetitions, the plus-one empirical p-value
of 0.001996 is the minimum attainable value; none of the simulated
placebo outcomes reached or exceeded the observed result.

These tests challenge simple null explanations. They do not reproduce
real execution or rule out every form of data mining, dependence,
misspecification, or regime risk.

#### Lag decay

| OFI lag setting (seconds) | Mean gross return (bps per trade) |
|---:|---:|
| 0 | 0.074850 |
| 1 | 0.058026 |
| 2 | 0.058346 |
| 5 | 0.021708 |
| 10 | 0.008105 |
| 30 | 0.003932 |

Gross returns generally declined at longer lags, consistent with a
short-lived relationship in this sample. The small non-monotonic
difference between the 1- and 2-second results means the decay is
not perfectly monotonic. These are development diagnostics, not a
separate strategy-selection exercise.


### 3.2 Conditional returns, activity and tail diagnostics

#### June 1-7, 2025: returns by OFI bucket

The table below groups observations by quantiles of the existing OFI
feature and reports the mean one-second forward last-trade-price return.
Because OFI has many repeated values, especially at -1 and +1, tied
quantile boundaries produce eight distinct intervals rather than ten
equally sized deciles.

| OFI interval | Observations | Mean OFI | Mean forward return (bps) | Zero-return share |
|---|---:|---:|---:|---:|
| (-1.001, -0.998] | 112,114 | -0.999914 | -0.032052 | 52.19% |
| (-0.998, -0.931] | 56,057 | -0.974757 | -0.077953 | 45.01% |
| (-0.931, -0.648] | 56,057 | -0.815914 | -0.033282 | 47.18% |
| (-0.648, -0.0702] | 56,057 | -0.372005 | -0.008296 | 48.94% |
| (-0.0702, 0.478] | 56,057 | 0.179962 | 0.010087 | 49.40% |
| (0.478, 0.895] | 56,057 | 0.717722 | 0.027810 | 47.82% |
| (0.895, 0.999] | 56,057 | 0.964842 | 0.086747 | 44.66% |
| (0.999, 1.0] | 112,114 | 0.999983 | 0.029667 | 51.17% |

All eight bucket medians are zero. Mean returns are generally more
negative in the negative-OFI buckets and more positive in the
positive-OFI buckets, but the relationship is not monotonic at the
extremes.

The pooled Pearson correlation is +0.096049, while Spearman correlation
is -0.179333. The large share of tied zero returns can affect rank
correlations, and rare large moves can affect conditional means.
Bid-ask bounce is another possible influence because targets use
last-trade prices rather than midpoint prices. These are plausible
mechanisms, not a definitive explanation of the sign difference; the
discrepancy remains a diagnostic limitation.

#### June 1-7, 2025: activity-conditioned sensitivity

The next table is a development-sample sensitivity analysis. The minimum
trade-count filters were not part of the frozen baseline and must not
be interpreted as a newly selected strategy.

| Minimum trades in decision second | Signals retained | Share of all decision times | Mean gross return (bps) | Win rate | 1% trimmed mean (bps) |
|---:|---:|---:|---:|---:|---:|
| 0 | 80,688 | 66.71% | 0.07485 | 36.08% | 0.07041 |
| 2 | 61,756 | 51.05% | 0.09633 | 38.02% | 0.09212 |
| 5 | 25,624 | 21.18% | 0.19983 | 45.07% | 0.19312 |
| 10 | 13,733 | 11.35% | 0.27870 | 50.03% | 0.27213 |

Requiring at least five trades in the decision second retains about
31.75% of the original June signals. Equivalently, about 68.25% of
baseline signals occurred in seconds with fewer than five trades.
The mean gross return rises with the activity threshold in this
sensitivity analysis, but the number of signals declines sharply.

This is evidence that activity conditioning is worth investigating,
not proof that it creates a viable strategy. The sensitivity was
examined on development data, and even a higher gross mean may remain
below actual trading costs. The September v1 baseline remains unchanged.

#### September 1-30, 2026: distribution and tail dependence

The frozen baseline generated 348,931 simulated trades. The median
gross return was zero, the gross win rate was 39.08%, and 28.46% of
trades had exactly zero returns. The mean positive return was
+0.86582 bps; the mean negative return was -0.74415 bps.

| Return quantile | Gross return (bps per trade) |
|---:|---:|
| 1st percentile | -3.693863 |
| 5th percentile | -1.637457 |
| 25th percentile | -0.001258 |
| 50th percentile (median) | 0.000000 |
| 75th percentile | +0.140101 |
| 95th percentile | +1.991397 |
| 99th percentile | +4.006361 |

The trimmed mean remains positive after symmetrically removing extreme
observations from both tails:

| Statistic | Mean gross return (bps per trade) |
|---|---:|
| Untrimmed mean | +0.096789 |
| 1% trimmed mean | +0.094129 |
| 5% trimmed mean | +0.087800 |

However, returns are tail-concentrated. The top 1% of trades (3,490
trades) contributed +20,189.39 when summing their per-trade gross
returns expressed in basis points, equivalent to 59.78% of the total
summed gross returns. The bottom 1% contributed -18,603.94 in the same
units, equivalent to -55.09% of the total summed gross returns.

These contribution statistics are sums of per-trade returns, not
portfolio P&L or notionally weighted profits. They are descriptive and
do not account for execution costs, overlap, capacity or the feasibility
of capturing extreme returns.

The trimmed means indicate that the positive average is not eliminated
by removing 5% from each tail. Nevertheless, the small mean, zero
median, low win rate and tail concentration all reinforce the need to
distinguish a gross predictive association from a reliable, executable
trading edge.

## 4. Frozen strategy specification

The baseline used for the June 8–30 and July evaluations, and frozen before the September evaluation, was:

- **Long:** OFI \(\geq +0.75\).
- **Short:** OFI \(\leq -0.75\).
- **Otherwise:** no trade.
- **Decision interval:** every five seconds, aligned to UTC timestamps whose second value is divisible by five.
- **Entry price proxy:** one second after feature availability.
- **Exit price proxy:** six seconds after feature availability, corresponding to five seconds of holding after the entry delay.
- **Price series:** last-trade-price series, forward-filled across no-trade seconds.
- **Activity filter:** none; no minimum trade-count filter is part of the frozen baseline.

Long returns follow the underlying price return; short returns reverse it. This is a simplified directional simulation, not a faithful execution model. It does not model order-book spread, queue position, market impact, latency, funding or borrow, or whether the assumed short exposure and fills could be implemented under a specific product's rules.

The frozen specification is recorded in `reports/frozen_strategy.md` and tagged in Git as `v1.0-frozen-ofi`. September's strategy results were not used to tune the thresholds or timing.

## 5. Strategy results across periods

| Evaluation period | Simulated trades | Mean gross return per trade | Median gross return | Gross win rate |
|---|---:|---:|---:|---:|
| 8–30 June 2025 (development) | 271,399 | +0.08437 bps | — | 37.29% |
| 1–31 July 2025 (later-period evaluation) | 364,634 | +0.072719 bps | 0.00000 bps | 36.22% |
| 1–30 September 2026 (historical holdout) | 348,931 | +0.096789 bps | 0.00000 bps | 39.08% |

The first two periods were part of development and earlier evaluation. The September 2026 period was reserved for a separate historical evaluation after the baseline tag had been created. It is important to keep this distinction clear: September is a retrospective historical holdout, not a live prospective forward test.

### 5.1 July 2025 details

- One-second rows: 2,678,400.
- Decision timestamps: 535,680.
- Threshold signals: 364,636; two lacked usable entry/exit price proxies.
- Executed trades: 364,634: 176,996 long and 187,638 short.
- Mean gross return: +0.072719 bps per trade.
- Gross win rate: 36.22%.
- Positive daily mean gross return: 31 of 31 days.
- Lowest / highest daily mean: +0.019055 / +0.122760 bps.
- Unweighted mean of daily means: +0.072600 bps.

A circular moving-block bootstrap over the 31 daily mean returns produced these descriptive 95% intervals:

| Resampled block length | 95% interval for mean daily gross return |
|---:|---:|
| 1 day | [0.063398, 0.081854] bps |
| 3 days | [0.061098, 0.084034] bps |
| 5 days | [0.059647, 0.085608] bps |

These intervals describe uncertainty in the mean of daily gross returns under the specified resampling design. They do not measure uncertainty in executable net returns, account for every possible regime change, or establish profitability after costs. July's correlation summaries were inspected before the strategy evaluation, so it should not be called a completely untouched preregistered holdout.

### 5.2 September 2026 historical holdout

The September dataset contained 2,592,000 one-second bars: 2,309,164 seconds with trades and 282,836 seconds without trades. The frozen baseline was applied without changing the signal threshold, decision grid, entry delay or holding period.

- Decision timestamps: 518,400.
- Threshold signals: 348,932; one signal was dropped for unavailable prices.
- Executed trades: 348,931: 190,040 long and 158,891 short.
- Mean gross return: +0.096789 bps per trade.
- Median gross return: 0.00000 bps per trade.
- Gross win rate: 39.08%.
- Positive daily mean gross returns: 30 of 30 days.
- Lowest / highest daily mean: +0.003708 / +0.161969 bps.
- Unweighted mean of daily means: +0.095398 bps.

Long trades had a mean gross return of +0.09097 bps and a 38.995% win rate. Short trades had a mean gross return of +0.10375 bps and a 39.173% win rate.

A moving-block bootstrap was applied to the 30 daily mean returns. The intervals below are for the **unweighted mean of daily means** (0.095398 bps), not the trade-weighted overall mean (0.096789 bps):

| Daily block length | Descriptive 95% interval for unweighted mean of daily means |
|---:|---:|
| 1 day | [0.082076, 0.108033] bps |
| 3 days | [0.079751, 0.110677] bps |
| 5 days | [0.081453, 0.109780] bps |

All three intervals are above zero. This supports a positive average gross return within this September sample under the chosen bootstrap procedure, but does not establish future persistence. There are only 30 daily observations, and the intervals remain dependent on the sample and resampling assumptions. They are not evidence of an executable trading edge.

## 6. Transaction-cost analysis

The mean gross return is the break-even round-trip cost under the simplified model, before omitted execution effects. For September, that threshold is just 0.096789 bps per trade.

### 6.1 Generic cost sensitivity

| Assumed round-trip cost | September mean net return per trade |
|---:|---:|
| 0.000 bps | +0.096789 bps |
| 0.025 bps | +0.071789 bps |
| 0.050 bps | +0.046789 bps |
| 0.075 bps | +0.021789 bps |
| 0.096789 bps | approximately 0.000000 bps |
| 0.100 bps | −0.003211 bps |
| 0.200 bps | −0.103211 bps |
| 1.000 bps | −0.903211 bps |
| 2.000 bps | −1.903211 bps |

These are mechanical sensitivity scenarios, not measured execution costs. They exclude spread, slippage, queue position, market impact, latency and fill uncertainty.

### 6.2 Published Spot fee comparisons

The official Binance Spot fee schedule was checked on 17 October 2026: [Binance Spot Trading Fee Rate](https://www.binance.com/en/fee/trading). The published rates include 0.10% per side for a regular user and 0.075% per side when the displayed BNB discount applies. Converted to round-trip basis points, these are 20 bps and 15 bps respectively. Applying those rates mechanically to the September mean gross return gives:

| Fee scenario | Round-trip fee assumption | September mean after fee alone |
|---|---:|---:|
| Regular Spot rate | 20.00 bps | −19.903211 bps per trade |
| Regular Spot rate with BNB discount | 15.00 bps | −14.903211 bps per trade |
| VIP 9 maker/maker, no BNB discount | 2.20 bps | −2.103211 bps per trade |
| VIP 9 maker/maker with BNB discount | 1.65 bps | −1.553211 bps per trade |

The VIP 9 examples are illustrative fee comparisons only. They require eligibility for the relevant tier, both executions to qualify as maker fills, and the applicable discount. Actual account fees can vary by tier, pair, promotions and fee-payment method. Maker fills are not guaranteed, and achieved fills may differ materially from the price proxies in this backtest.

**The strategy does not survive the assessed Spot fee scenarios.** Fees alone exceed the observed mean gross edge, even before adding spread and execution costs. Therefore, the tested implementation is not economically viable under these assumptions.

## 7. Limitations and interpretation

1. **Last-trade prices are not executable quotes.** The model uses last-trade-price proxies rather than historical bid/ask midpoint or actual fill prices. It cannot isolate midpoint movement from all bid–ask bounce effects.
2. **Inactive seconds create repeated prices.** Forward-filling the last trade price introduces zero returns when no trade changes the price; approximately 49% of one-second returns in the broader June exploratory sample were zero.
3. **Execution is not modelled.** Spread, slippage, queue position, market impact, latency, partial fills, rejected orders and actual order-fill probabilities are absent.
4. **Short exposure is simplified.** A short signal is simulated by reversing the underlying return; an actual implementation requires an appropriate product or venue, and its own execution, fee, borrow or funding assumptions.
5. **Inference remains limited.** Daily-block bootstrap intervals are descriptive and based on 23, 30 or 31 daily observations depending on the period. They cannot guarantee regime stability or eliminate all specification and data-snooping risk.
6. **Historical holdout is not a live forward test.** September 2026 was held out from the earlier 2025 development work and evaluated after the baseline was tagged, but it is still a historical retrospective analysis.
7. **The gross compounded return is not an investable performance claim.** The strategy does not specify a defensible account-level capital allocation or demonstrate executable reinvestment, so a frictionless compounded figure is not presented as expected or achievable performance.
8. **Generalisation is unknown.** The study concerns BTCUSDT on one venue and a limited set of historical periods. It does not establish stability across other assets, venues, or market regimes.

## 8. Conclusion and future research

In the examined historical samples, aggressive-volume imbalance was positively associated with average future last-trade-price returns, and the fixed-threshold strategy showed small positive mean gross returns. The September 2026 historical holdout produced a mean gross return of 0.096789 bps per trade, with positive daily means on all 30 days and positive descriptive daily-block bootstrap intervals.

However, the break-even round-trip cost is only 0.096789 bps per trade. The assessed Spot fee scenarios exceed that edge by a substantial margin, before spread and execution uncertainty. Last-trade-price simulations do not establish achievable fills.

**The tested strategy is not economically viable under the assessed transaction costs, and the study does not establish an executable trading edge.** This is the main conclusion, not a failure of the project: the study distinguishes statistical association from net profitability and documents why the apparent gross edge is insufficient.

One possible future research direction is to study whether OFI adds value as an input to a market-making or quote-skew model, where the signal may be used for inventory or quoting decisions rather than as a standalone taker-like directional trade. That would be a new hypothesis requiring order-book quotes, execution modelling, a separate methodology and an independent evaluation. The current findings do not establish that such a strategy would work.

## 9. Reproducibility

### Frozen baseline provenance

- Annotated Git tag: `v1.0-frozen-ofi`
- Tag creation time: `2026-10-17T20:56:35+01:00`
- Tagged commit: `02d867a5d395a16d43dac1aaccfe320188eb53b3`
- Annotated tag object: `c95b4552b7b834db75a3177b3da6cc30b96927bd`
- Frozen strategy specification: `reports/frozen_strategy.md`

The tag identifies the baseline code snapshot used before the September
2026 historical holdout evaluation. September is a retrospective
historical holdout, not a live forward test.



The main scripts include:

- `run_research.ps1` — orchestrates the download, dataset construction, backtest, final evaluation and automated tests for a specified date range.
- `src/download_range.py` — downloads daily Binance aggregate-trade archives for the configured dates.
- `src/build_multiday_dataset.py` — builds one-second bars and forward-return targets for the configured dates.
- `src/backtest.py` — implements the frozen threshold rule and per-trade cost sensitivity analysis.
- `src/final_evaluation.py` — summarises trade results and bootstraps daily mean returns.
- `src/diagnose_signal.py`, `src/diagnose_targets.py`, `src/analyse_buckets.py` — exploratory signal and target diagnostics.
- `src/audit_sampling.py` — checks the five-second decision sampling.
- `src/predictive_controls.py` and `src/placebo_and_timing_checks.py` — regression controls, placebo checks and timing diagnostics.
- `src/supplemental_trade_flow_analysis.py` — produces conditional-return and September trade-tail diagnostics and figures.
- `tests/test_backtest.py` and `tests/test_research_data_functions.py` — automated tests for backtest mechanics, data transformations and target alignment.

### Reproducing the main pipeline

The project uses Python and a local virtual environment. On Windows, create the environment and install the development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Run the complete main pipeline for the September 2026 evaluation:

```powershell
.\run_research.ps1
```

The runner defaults to 1–30 September 2026. To evaluate another date range, pass the dates explicitly. For example:

```powershell
.\run_research.ps1 -StartDate "2025-06-01" -EndDate "2025-06-07"
```

The runner downloads the required daily archives, builds the one-second dataset and forward-return targets, runs the backtest and final evaluation, and executes the automated test suite. It requires an internet connection for archives that are not already available locally.

The supplementary diagnostic script can be run separately when the relevant datasets have been generated:

```powershell
.\.venv\Scripts\python.exe src\supplemental_trade_flow_analysis.py
```

Raw archives, generated datasets and result CSV files are intentionally kept out of Git. The source code, tests, reports, figures and experiment documentation are version-controlled.

The automated test suite passed **10 tests** during the final project checks.
