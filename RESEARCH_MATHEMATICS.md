# Trading Algorithm: Mathematics and Validation

This document describes the mathematics currently used by the rules-based
research strategy, its risk diagnostics, the backtest accounting, and the
validation tests. Equations use GitHub-compatible LaTeX delimiters:
`$...$` for inline expressions and `$$...$$` for display expressions.

This is a research and teaching system, not investment advice. A backtest
cannot establish that a strategy will make money in the future.

## 1. Data and timing

The system downloads adjusted daily prices. For a symbol $i$, let
$P_{i,t}$ be the adjusted close on trading day $t$. Daily simple return is:

$$
r_{i,t} = \frac{P_{i,t}}{P_{i,t-1}} - 1.
$$

Signals are sampled weekly using Friday observations. The strategy does not
use the return from the signal date to represent a same-day fill. Backtest
returns use the prior day's holdings:

$$
r_{p,t}^{\text{gross}} =
\sum_i w_{i,t-1}r_{i,t}.
$$

This one-period lag is intended to prevent trading at a price that was not
available when the signal was calculated.

The current dataset contains current S&P 500 constituents, non-S&P ETFs,
forex, bonds, commodities, and a small explicit list of failed or delisted
symbols. The latter list is not a survivorship-bias-free security master:
Yahoo Finance does not provide complete histories for every failed security.
Current constituents applied backward through history still create
survivorship bias.

## 2. Momentum signal

The default cross-sectional score is trailing momentum with a skip period:

$$
m_{i,t} =
\frac{P_{i,t-s}}{P_{i,t-L}} - 1,
$$

where:

- $L$ is the lookback window, currently 126 trading days;
- $s$ is the skip window, currently 21 trading days in the balanced profile;
- the aggressive profile uses a 5-day skip window.

The skip period avoids ranking securities on the most recent short-term move,
which can be affected by short-term reversal and the exact execution date.
At each weekly rebalance, symbols are ranked by $m_{i,t}$ and the top $N$
eligible symbols are selected.

Symbols are excluded if:

1. their momentum score is unavailable;
2. their rolling volatility is unavailable or non-positive;
3. their trailing stop is triggered;
4. they are in an excluded asset-class list for the equity-focused notebook.

## 3. Volatility estimation

For a rolling window of $V$ trading days, annualized volatility is estimated
as:

$$
\hat{\sigma}_{i,t}
 =
\sqrt{252}\,
\operatorname{StdDev}
\left(r_{i,t-V+1},\ldots,r_{i,t}\right).
$$

The factor $\sqrt{252}$ annualizes a daily standard deviation under the
usual approximation of 252 trading days per year.

If the most recent observation is missing but a prior rolling estimate exists,
the implementation forward-fills the volatility estimate. This prevents one
missing quote from removing an otherwise valid security from the ranking.
It does not invent a new price return.

The portfolio's rolling volatility uses the same estimator applied to the
weighted portfolio return series:

$$
\hat{\sigma}_{p,t}
 =
\sqrt{252}\,
\operatorname{StdDev}
\left(r_{p,t-V+1},\ldots,r_{p,t}\right).
$$

## 4. Inverse-volatility weighting

For selected symbols, raw risk-adjusted scores are proportional to inverse
volatility:

$$
\tilde{w}_{i,t} = \frac{1/\hat{\sigma}_{i,t}}
{\sum_{j \in S_t}1/\hat{\sigma}_{j,t}},
$$

where $S_t$ is the selected set.

The target exposure is:

$$
E_t =
\min(E_{\max}, E_{\text{regime},t}),
$$

where $E_{\max}$ is the maximum equity exposure and $E_{\text{regime},t}$ is
the drawdown-controlled exposure described below.

The desired uncapped weight is $E_t\tilde{w}_{i,t}$. Each position is capped
at $w_{\max}$. The implementation repeatedly fixes positions above the cap at
$w_{\max}$ and reallocates their excess to the uncapped positions. Therefore,
the cap does not silently turn permitted exposure into cash.

The concentration diagnostic is an HHI-style measure:

$$
\operatorname{HHI}_t = \sum_i w_{i,t}^2.
$$

For equal weights across $n$ positions, $\operatorname{HHI}=1/n$. Larger
values indicate greater concentration.

## 5. Stop-loss and eligibility controls

For each symbol, the rolling high over the volatility window is:

$$
H_{i,t} = \max(P_{i,t-V+1},\ldots,P_{i,t}).
$$

The symbol is excluded when:

$$
P_{i,t} < H_{i,t}(1-\ell),
$$

where $\ell$ is the configured stop-loss percentage.

This is a signal-level exclusion, not a broker stop order. It is evaluated
using historical prices at the rebalance and does not guarantee an execution
at the stop threshold.

## 6. Portfolio exposure and drawdown defense

The benchmark drawdown is:

$$
D_t =
1-\frac{P_{b,t}}{\max_{u\leq t}P_{b,u}}.
$$

The regime exposure starts at 100% and declines linearly after the configured
drawdown threshold:

$$
E_{\text{regime},t}
=
\operatorname{clip}\left(
1-\frac{D_t-D_{\text{start}}}
{D_{\text{full}}-D_{\text{start}}},
E_{\text{defensive}},
1
\right).
$$

Here:

- $D_{\text{start}}$ is the drawdown at which reduction begins;
- $D_{\text{full}}$ is the drawdown at which the defensive floor is reached;
- $E_{\text{defensive}}$ is the minimum exposure floor.

This is a risk-control heuristic, not an optimal-control solution. It can
reduce losses in some bear markets and also reduce participation during
recoveries.

## 7. Transaction costs and slippage

Let one-way cost in basis points be:

$$
c_{\text{bps}} =
c_{\text{commission}}+
c_{\text{half-spread}}+
c_{\text{slippage}}+
c_{\text{impact}}.
$$

The decimal cost rate is $c=c_{\text{bps}}/10{,}000$. Portfolio turnover is:

$$
\tau_t = \sum_i |w_{i,t}-w_{i,t-1}|.
$$

The backtest subtracts estimated costs:

$$
r_{p,t}^{\text{net}}
 =
r_{p,t}^{\text{gross}}-\tau_t c.
$$

Current default assumptions are 1.0 bps commission, 2.5 bps half-spread,
5.0 bps slippage, and 2.0 bps market impact, totaling 10.5 bps per unit of
turnover. These are simplified proportional costs; actual impact depends on
volume, liquidity, order size, and market conditions.

Portfolio equity is compounded as:

$$
V_t = V_{t-1}(1+r_{p,t}^{\text{net}}).
$$

The trade ledger separately records notional value, estimated cost, realized
profit/loss, net profit/loss, and cumulative net profit/loss.

## 8. Performance ratios and risk diagnostics

Total return:

$$
R_{\text{total}} = \frac{V_T}{V_0}-1.
$$

Annualized return, using elapsed calendar years $Y$:

$$
R_{\text{annual}} =
\left(\frac{V_T}{V_0}\right)^{1/Y}-1.
$$

Annualized volatility:

$$
\sigma_{\text{annual}} =
\operatorname{StdDev}(r_{p,t})\sqrt{252}.
$$

Sharpe ratio, using zero as the risk-free return approximation:

$$
\operatorname{Sharpe} =
\frac{\operatorname{Mean}(r_{p,t})}
{\operatorname{StdDev}(r_{p,t})}\sqrt{252}.
$$

Maximum drawdown:

$$
\operatorname{MDD}
=
\min_t\left(\frac{V_t}{\max_{u\leq t}V_u}-1\right).
$$

Rolling portfolio Sharpe uses a 63-day window:

$$
\operatorname{Sharpe}_{p,t}^{(63)}
=
\frac{\operatorname{Mean}_{63}(r_{p})}
{\operatorname{StdDev}_{63}(r_{p})}\sqrt{252}.
$$

For an asset $i$ relative to benchmark $b$, rolling beta and correlation are:

$$
\beta_{i,b}
=
\frac{\operatorname{Cov}(r_i,r_b)}
{\operatorname{Var}(r_b)},
\qquad
\rho_{i,b}
=
\operatorname{Corr}(r_i,r_b).
$$

Downside volatility is estimated from negative returns in the rolling
window:

$$
\sigma_{\text{downside}}
=
\sqrt{252}\,
\operatorname{StdDev}\left(r_t\;|\;r_t<0\right).
$$

The risk report's expected-return proxy is lagged six-month momentum scaled
to a one-year horizon and clipped:

$$
\widehat{\mu}_i
=
\operatorname{clip}\left(
\frac{m_i}{\sqrt{126/252}},
-1,1
\right).
$$

For a forecast horizon $h$:

$$
\widehat{\Pi}_i = \widehat{\mu}_i\frac{h}{252},
\qquad
\widehat{L}_i =
\hat{\sigma}_i\sqrt{\frac{h}{252}},
\qquad
\operatorname{Reward/Risk}_i =
\frac{\widehat{\Pi}_i}{\widehat{L}_i}.
$$

The displayed forecast Sharpe is currently the same expected
profit-to-expected-loss ratio. It is an ex-ante proxy, not a realized Sharpe
ratio and not a calibrated probability forecast.

## 9. Validation tests currently run

The repository currently runs nine automated tests with `pytest`.

### Unit and accounting tests

- Performance report formatting checks dollar and percentage precision.
- Trade ledger checks buy/sell sides, notional values, realized P/L, and net
  P/L after costs.
- Risk diagnostics checks expected-return, volatility, reward/risk, and
  forecast-Sharpe outputs.
- Period filtering checks date boundaries and monthly return aggregation.
- Buy-and-hold checks that a rising benchmark produces rising equity.

### Strategy integrity tests

- Position weights are non-negative.
- Position weights do not exceed the configured cap.
- Total exposure does not exceed the configured maximum.
- Capped inverse-volatility allocations redistribute weight rather than
  silently leaving excess cash.
- Explicitly excluded symbols are never selected.
- A missing recent quote does not eliminate all otherwise valid signals.
- Benchmark fallback can produce a benchmark holding when no candidate is
  eligible.

### Look-ahead and robustness diagnostics

The robustness script additionally:

1. Multiplies prices strictly after a mutation date by 17.
2. Recomputes all signals.
3. Verifies that weights before the mutation date do not change.

It reports independent results for 2012–2016, 2016–2020, 2020–2023, and
2023–2026; predefined bull and bear windows; buy-and-hold SPY and QQQ; and
baseline versus high-cost scenarios.

These tests detect several classes of implementation error, but they do not
prove the absence of all leakage. They do not replace point-in-time
constituent data, delisted-security data, walk-forward parameter selection,
paper trading, or live execution monitoring.

## 10. Interpreting benchmark comparisons

Beating SPY over the same historical interval is not enough to establish a
valid strategy. A credible comparison should:

1. Use the same start/end dates and adjusted-price convention.
2. Apply realistic costs to both portfolios.
3. Use only information available at each decision time.
4. Compare multiple non-overlapping periods and market regimes.
5. Report volatility, drawdown, turnover, and concentration alongside return.
6. Reserve a final untouched test period for evaluation.

The current project deliberately reports when the rules-based strategy does
not beat SPY rather than changing assumptions until it does. Parameter
optimization should be performed only on a training period and then checked
on later unseen data.
