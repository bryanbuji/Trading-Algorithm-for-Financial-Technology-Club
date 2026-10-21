# Trading Algorithm for Financial Technology Club

This project is a weekly, long-only multi-asset research system. It combines
cross-sectional momentum, volatility-adjusted position sizing, a broad-market
trend regime, trailing stop-loss filtering, transaction costs, and drawdown
exposure controls. It now reports mathematically defined expected-return
proxies, volatility, downside volatility, beta, correlation, reward/risk,
portfolio Sharpe, and concentration. An optional ML workflow is provided
separately. It is
designed for teaching and reproducible research; it does not place live
brokerage orders.

## Requirements

- macOS, Linux, or Windows
- Python 3.15
- Internet access for Yahoo Finance data downloads

Check your Python installation:

```sh
python3.15 --version
```

## One-time setup

Run these commands from Terminal after cloning the repository. The project
does not require an Alpha Vantage key. The project-local `.venv` is ignored by
Git and must be created locally on each computer:

```sh
git clone <repository-url>
cd Trading-Algorithm-for-Financial-Technology-Club
python3.15 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user \
  --name trading-research \
  --display-name "Python (trading-research)"
```

The pandas 3.x dependency requires Python 3.15 in this project setup. Remove
the local environment only when you intentionally want to recreate it.

## Start JupyterLab

Start JupyterLab with the project environment:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club
.venv/bin/python -m jupyterlab
```

JupyterLab opens in a browser at a localhost URL. In JupyterLab:

1. Open `notebooks/01_data_download.ipynb`.
2. Select the `Python (trading-research)` kernel.
3. Choose **Kernel → Restart Kernel and Run All Cells**.
4. Confirm that it reports approximately `3,700 dates x 505 symbols`.
5. Open `notebooks/02_backtest_baseline.ipynb`.
6. Choose **Kernel → Restart Kernel and Run All Cells**.
7. In the first code cell, leave `plot_start` and `plot_end` as `None` to
   display the full history. Set both values, for example
   `plot_start = "2020-01-01"` and `plot_end = "2020-12-31"`, only when you
   want a focused chart.

The first notebook downloads adjusted daily prices for the configured
equities, forex, bonds, commodities, and explicit historical-symbol lists and
saves them to
`data/processed/prices.parquet`. The second notebook uses that cached data and
prints the rules-based report, plots portfolio value
and drawdown over time, marks buy/sell activity, and displays a table containing every simulated
trade with its date, symbol, side, weights, execution price, notional value,
estimated trading cost, realized profit/loss, net profit/loss, trade return,
and cumulative net profit/loss. It also shows configurable full-history,
arbitrary date-range, annual, monthly, and five-year views for equity,
returns, trade count, traded notional, P/L, drawdown, exposure, volatility,
positions, concentration, and Sharpe.
The optional ML workflow has its own notebook, runner, and dependency file in
[Machine Learning Trade Model/](./Machine%20Learning%20Trade%20Model/README.md).

### Minimal command-line workflow

The following commands download the Yahoo Finance cache, run the tests, run
the direct backtest, and run the robustness audit. None of these commands
requires Alpha Vantage:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club

# Download the configured Yahoo Finance universe.
PYTHONPATH=src .venv/bin/python - <<'PY'
from trading.config import load_config
from trading.data import configured_symbols, download_prices

config = load_config()
download_prices(configured_symbols(config), config["start_date"])
PY

# Verify the project.
PYTHONPATH=src .venv/bin/python -m pytest -q tests

# Run the backtest and print its performance report.
PYTHONPATH=src .venv/bin/python - <<'PY'
from trading.config import load_config
from trading.data import load_prices
from trading.strategy import weekly_momentum_weights
from trading.backtest import format_performance_report, run_backtest

config = load_config()
prices = load_prices()
weights = weekly_momentum_weights(
    prices,
    config["benchmark"],
    config["top_n"],
    config["lookback_days"],
    config["skip_days"],
    config["volatility_days"],
    config["max_position_weight"],
    config["max_equity_exposure"],
    config["defensive_exposure"],
    config["stop_loss_pct"],
    config["drawdown_start"],
    config["drawdown_full_defense"],
    rebalance_frequency=config["frequency"],
)
ledger, holdings, trades = run_backtest(
    prices,
    weights,
    config["initial_capital"],
    config["commission_bps"],
    config["half_spread_bps"],
    config["slippage_bps"],
    config["market_impact_bps"],
)
print(format_performance_report(ledger, config["initial_capital"]))
print(f"Trades recorded: {len(trades):,}")
PY

# Run look-ahead, regime, benchmark, and cost-sensitivity checks.
PYTHONPATH=src .venv/bin/python scripts/robustness_audit.py
```

If the Yahoo cache already exists, omit the download command and run the
tests, backtest, or notebooks directly.

### Switch to daily rebalancing

Edit [config.yaml](./config.yaml) and change:

```yaml
frequency: "D"
```

`"D"` means rebalance on every available trading date. The default
`"W-FRI"` means rebalance using Friday observations. The strategy, the ML
feature panel, the ML predictions, and the audit scripts read this setting.
After changing it, rerun the backtest or ML command; no data-download change
is required.

The rules notebook supports `conservative`, `balanced`, and `aggressive`
risk profiles. Set `risk_profile` in its first code cell and rerun all cells.
The profile changes exposure, position caps, volatility targeting, and
stop-loss tolerance; it does not change the signal universe.

The allocation logic now redistributes weight after applying position caps.
Previously, inverse-volatility weights were capped without redistribution,
which could leave a permitted 100% portfolio exposure with only 50–60%
invested. That underinvestment was a primary cause of the unexpectedly low
return and low trade count after the universe expansion.
Non-positive observations, such as the negative front-month crude-oil futures
settlement in April 2020, are converted to missing values because ordinary
percentage-return math is undefined across zero. A futures-specific continuous
contract model is required to include those observations faithfully.

## Run without JupyterLab

This command runs the test suite:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club
PYTHONPATH=src .venv/bin/python -m pytest -q tests
```

To run the robustness audit:

```sh
PYTHONPATH=src .venv/bin/python scripts/robustness_audit.py
```

The audit checks that future price mutations cannot change earlier signals,
reports the requested 2012-2016, 2016-2020, 2020-2023, and 2023-2026 windows,
tests defined bull/bear regimes, compares against buy-and-hold `SPY`, and
reruns the strategy under higher execution costs.

To run the backtest directly:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club
PYTHONPATH=src .venv/bin/python - <<'PY'
from trading.config import load_config
from trading.data import load_prices
from trading.strategy import weekly_momentum_weights
from trading.backtest import format_performance_report, run_backtest

config = load_config()
prices = load_prices()
weights = weekly_momentum_weights(
    prices,
    config["benchmark"],
    config["top_n"],
    config["lookback_days"],
    config["skip_days"],
    config["volatility_days"],
    config["max_position_weight"],
    config["max_equity_exposure"],
    config["defensive_exposure"],
    config["stop_loss_pct"],
    config["drawdown_start"],
    config["drawdown_full_defense"],
)
ledger, holdings, trades = run_backtest(
    prices,
    weights,
    config["initial_capital"],
    config["commission_bps"],
    config["half_spread_bps"],
    config["slippage_bps"],
    config["market_impact_bps"],
)
print(format_performance_report(ledger, config["initial_capital"]))
print(f"Trades recorded: {len(trades):,}")
PY
```

## Change the experiment

Edit [config.yaml](./config.yaml), then rerun the backtest notebook or the
direct command. Useful teaching experiments include:

```yaml
top_n: 5
max_position_weight: 0.05
stop_loss_pct: 0.10
drawdown_start: 0.05
```

After changing `symbols` or the asset-class lists, rerun `01_data_download.ipynb`
before running the backtest. The default universe combines current S&P 500 constituents, broad asset-class
proxies, additional non-S&P international and thematic ETFs, and a small
explicit list of historically failed or delisted symbols.
The failed-symbol list is not comprehensive and Yahoo Finance may not provide
complete histories for those tickers. Current constituents are still applied
backward through history, so survivorship bias remains unless a point-in-time
security master and delisted-price source are supplied.
When an asset has no observations after a period in which it was held, the
pandas backtester treats the first date after a five-observation trailing gap as
a delisting liquidation at zero rather than silently carrying the position at
an unchanged value. This avoids mistaking a one-day vendor delay for a
delisting. It does not replace a point-in-time delisted-price feed.

## Free delisted-company data

There is no complete, point-in-time, survivorship-bias-free US equity database
with adjusted prices that is both freely redistributable and available through
a simple public API. The project therefore does not claim that its Yahoo
Finance cache is delisted-security data.

Potential free research sources are documented below, but each requires
validation before use:

- SEC EDGAR company submissions and filings: free official metadata, but not a
  ready-made delisted-price database. The integration uses `data.sec.gov` and
  requires an identifying `SEC_USER_AGENT` containing a name and email.
- CRSP/Compustat and Norgate: appropriate survivorship-bias-controlled sources,
  but not free for this use.
- Stooq and public exchange archives: sometimes retain symbols after delisting,
  but coverage, corporate actions, and redistribution rights vary.
- Alpha Vantage: offers a free API tier for optional adjusted prices, but
  requires `ALPHAVANTAGE_API_KEY`, has strict quotas, and does not guarantee
  delisted-company coverage.
- FRED: genuinely free public benchmark and macroeconomic series; it does not
  provide individual-company prices.
- GitHub datasets: useful for experiments only after checking provenance and
  licensing; many are scraped, incomplete, or survivorship-biased.

The current project keeps a small explicit failed-symbol list and reports the
limitation rather than silently treating it as a complete delisted universe.
Before using any free source, record its license, symbol membership dates,
price adjustment method, listing date, delisting date, and missing-data policy.

The optional adapters are in
[src/trading/open_data.py](./src/trading/open_data.py). Download selected
research data with:

```sh
# Optional only: add Alpha Vantage adjusted prices to the existing Yahoo cache.
# The normal download, notebooks, tests, and backtest work without this.
export ALPHAVANTAGE_API_KEY="your-key"
PYTHONPATH=src python3.15 scripts/download_open_data.py \
  --merge-alpha-symbol SIVB \
  --merge-alpha-symbol FRC
```

The merge adds missing symbols and fills missing observations without
overwriting non-missing Yahoo values. It updates
`data/processed/prices.parquet` in place. You can also set
`alpha_vantage_symbols` in `config.yaml`; the data-download notebook performs
the same merge automatically after downloading Yahoo prices.

```yaml
alpha_vantage_symbols:
  - SIVB
  - FRC
```

# FRED benchmark/macro series; no FRED API key is required for CSV downloads.
```sh
PYTHONPATH=src python3.15 scripts/download_open_data.py \
  --fred-series SP500 --fred-series VIXCLS

# SEC submissions and XBRL company facts; use an identifying name and email.
export SEC_USER_AGENT="Research Name research@example.com"
PYTHONPATH=src python3.15 scripts/download_open_data.py \
  --sec-cik 320193
```

FRED and SEC files are written to ignored `data/external/`. Alpha Vantage is a
supplement to the Yahoo cache, not a point-in-time delisted universe. SEC
outputs provide event and company metadata that must be joined with a price
source.

## LEAN audit

An independent QuantConnect LEAN implementation is maintained in the sibling
repository [LEAN based trading algorithm FINTECH](</Users/buji/Projects/LEAN%20based%20trading%20algorithm%20FINTECH/>).
It reproduces the weekly signal cadence, next-session execution, top-five
momentum selection, inverse-volatility sizing, position caps, and SPY fallback.
It requires the LEAN CLI (installed with `pipx`), Docker, and LEAN-compatible
licensed data; this project's Yahoo Finance Parquet files are not automatically
valid LEAN data.

Run the pandas provenance audit before comparing engines:

```sh
PYTHONPATH=src .venv/bin/python scripts/provenance_audit.py
```

On the locally downloaded 586-symbol universe, the current profiles produced
these illustrative results:

| Profile | Total return | Annualized return | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| Conservative | -0.395% | -0.027% | -0.023 | -3.973% |
| Balanced | 1.755% | 0.118% | 0.080 | -5.172% |
| Aggressive | 1.890% | 0.127% | 0.088 | -4.751% |

These are not forecasts. They show that the sizing fix improves the result
from the prior 0.6% run, but the strategy still does not approach the former
2250% result. The earlier result should remain treated as invalid until it can
be reproduced with point-in-time data, realistic execution, and independent
validation.

The aggressive profile is deliberately the highest-return candidate found in
the current exploratory comparison, but it still does not beat full-period
buy-and-hold SPY after costs. The project does not silently tune parameters
against the complete history just to manufacture a benchmark beat; use
walk-forward optimization before selecting production parameters.

For a serious survivorship-bias study, replace `historical_symbols` with a
point-in-time universe from CRSP, Compustat, Norgate, or another provider that
retains delisted securities and corporate actions. Do not interpret the
hand-curated list as survivorship-bias-free.

## Project defaults

- Historical start date: `2012-01-01`
- Signals and rebalancing: weekly
- Direction: long-only (`direction: long_only`)
- Initial capital: `$100,000`
- Position cap: `10%`
- Maximum equity exposure: `100%`
- Costs: commission, half-spread, slippage, and market impact
- Signal execution: next trading day after the Friday close (`1` day lag)
- Drawdown control: exposure reduces progressively after `10%` drawdown and
  reaches the defensive floor at `25%`
- Forecast horizon: `21` trading days
- Volatility target: `20%` annualized
- Optional ML comparison: a lagged-feature regularized Ridge model evaluated
  with walk-forward predictions in the separate ML folder

## Mathematical diagnostics

The risk layer uses daily adjusted-price returns and annualizes volatility with
`standard deviation × sqrt(252)`. It reports:

- **Expected return proxy:** lagged 6-month momentum scaled to a one-year
  horizon and clipped to avoid unbounded forecasts.
- **Expected profit:** expected return scaled to the configured forecast
  horizon.
- **Expected loss:** annualized volatility scaled by the square root of the
  forecast horizon.
- **Reward/risk:** expected profit divided by expected loss.
- **Forecast Sharpe:** the same ex-ante reward/risk proxy; it is not a realized
  Sharpe ratio.
- **Portfolio Sharpe:** rolling annualized mean return divided by rolling
  standard deviation.
- **Concentration:** the sum of squared position weights (HHI-style measure).

The optional ML workflow uses lagged momentum, volatility, relative strength,
and benchmark-volatility features. It retrains chronologically and reports the
out-of-sample prediction/realized-return correlation. Install its separate
requirements and follow [Machine Learning Trade Model/README.md](./Machine%20Learning%20Trade%20Model/README.md).
It is intentionally simple and is not evidence that future returns are
predictable.

## Interpreting the unusually high return

A 3,750% total return over 14 years is approximately a 28% annualized return,
not a guaranteed 37-fold annual profit rate. It should be treated as a
research alert, not a result to trust automatically. The default universe is
the current S&P 500 membership applied backward over the full history. That
creates survivorship bias because failed, acquired, and removed companies are
not represented. Yahoo Finance adjusted prices, missing/delisted securities,
execution timing, liquidity, and simplified market-impact assumptions can also
materially affect results.

Use the segmented/regime output, leakage test, cost sensitivity, and
buy-and-hold comparison before drawing conclusions. A return increase after
2022 is not considered validated merely because it reproduces; inspect its
period concentration, turnover, symbols, and cost sensitivity. Point-in-time
constituent membership and a licensed survivorship-bias-controlled data source
are required for production-quality research.

## Troubleshooting

### `python: command not found`

Create the environment with `python3.15`, then activate it before using
`python`.

### `jupyter: command not found`

Use the project-local interpreter:

```sh
.venv/bin/python -m jupyterlab
```

### `ModuleNotFoundError: No module named 'trading'`

Run the notebook from this project or use the included notebooks, which locate
the project automatically. For terminal commands, include `PYTHONPATH=src`.

### `NotOpenSSLWarning`

This warning comes from the macOS system Python SSL library. It does not
prevent the research workflow from running. A newer Python installation can
remove the warning.

### ML overflow or invalid `matmul` warnings

The standalone ML workflow cleans non-finite prices, clips extreme feature
and target values, skips unusable training windows, and clips predictions to a
bounded return range. Run the notebook in the ML folder with a fresh kernel.
Missing predictions for symbols without enough history are expected and are
excluded from ranking.

## Important limitations

This is not investment advice and is not a live trading system. Backtests can
be wrong because of survivorship bias, data errors, stale prices, liquidity
constraints, execution assumptions, and model overfitting. Review results
with walk-forward and out-of-sample validation before considering paper
trading.
