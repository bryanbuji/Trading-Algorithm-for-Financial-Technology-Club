# Trading Algorithm for Financial Technology Club

This project is a weekly, long-only multi-asset research system. Its Yahoo
Finance universe includes today's S&P 500 constituents and the configured ETF
lists, giving the ranker hundreds of stock candidates. It combines
cross-sectional momentum, volatility-adjusted position sizing, a broad-market
trend regime, trailing stop-loss filtering, transaction costs, and drawdown
exposure controls. It now reports mathematically defined expected-return
proxies, volatility, downside volatility, beta, correlation, reward/risk,
portfolio Sharpe, and concentration. See [STRATEGY.md](STRATEGY.md) for the
signals, ranking, sizing, and risk controls. An optional ML workflow is
provided separately. It is
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
4. Confirm that it prints the current date range and panel dimensions. Counts
   vary with configured symbols, provider coverage, and listing dates.
5. Open `notebooks/02_backtest_baseline.ipynb`.
6. Choose **Kernel → Restart Kernel and Run All Cells**.
7. In the first code cell, leave `plot_start` and `plot_end` as `None` to
   display the full history. Set both values, for example
   `plot_start = "2020-01-01"` and `plot_end = "2020-12-31"`, only when you
   want a focused chart.

The first notebook downloads adjusted daily prices for the configured
equities, forex, bonds, commodities, historical S&P 500 constituents, current
S&P 500 members, and explicit failed-symbol lists, then saves them to
`data/processed/prices.parquet`. It also saves dated membership masks to
`data/processed/universe_membership.parquet`; the strategy uses these to admit
S&P 500 stocks only while the public history says they were members. The
second notebook uses that
cache, prints the rules-based report, plots portfolio value and drawdown,
marks buy/sell activity, and shows a formatted 100-row trade preview with
execution date, symbol, side, weights, execution price, notional value,
estimated cost, realized/net P&L, trade return, and cumulative net P&L. It also
shows configurable full-history,
arbitrary date-range, annual, monthly, and five-year views for equity,
returns, trade count, traded notional, P/L, drawdown, exposure, volatility,
positions, concentration, and Sharpe.
The full ledger is saved to ignored `data/processed/trades.csv` and includes
signed `cash_flow` and
`cumulative_cash_flow` columns. Use these for cash-movement auditing; buys are
negative cash flow; sells are usually positive after costs, except a zero-value
delisting exit. These are estimated from weight changes, not a cash balance.
The notebook includes a 12-bar monthly cash-flow chart whose year can be
changed in the `plot_monthly_cash_flow(trades, year=...)` call.
The optional ML workflow has its own notebook, runner, and dependency file in
[Machine Learning Trade Model/](./Machine%20Learning%20Trade%20Model/README.md).

### Minimal command-line workflow

The following commands download the Yahoo Finance cache, run the tests, and
run the robustness audit. None requires Alpha Vantage:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club

# Download the configured Yahoo Finance universe.
PYTHONPATH=src .venv/bin/python - <<'PY'
from trading.config import load_config
from pathlib import Path
from trading.data import load_configured_market_data

config = load_config()
load_configured_market_data(config, Path.cwd(), refresh_yahoo=True)
PY

# Verify the project.
PYTHONPATH=src .venv/bin/python -m pytest -q tests

# Run look-ahead, regime, benchmark, and cost-sensitivity checks.
PYTHONPATH=src .venv/bin/python scripts/robustness_audit.py
```

If the Yahoo cache already exists, omit the download command and run the
tests, backtest, or notebooks directly. In JupyterLab, use **Kernel →
Restart Kernel and Run All Cells** after changing `config.yaml`; rerunning
only the final plotting cells reuses the previous `weights`, `ledger`, and
`trades` variables.

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
The selected profile overrides `top_n`, exposure, position limits, volatility
target, and stop-loss settings where it defines them. Change those values in
the selected profile, or set `risk_profile` to a profile with the desired
values; changing only the top-level copy will not override a profile value.
The profile changes exposure, position caps, volatility targeting, and
stop-loss tolerance; it does not change the signal universe.

The balanced profile ranks up to 20 positions and caps each at 5%. The
allocator redistributes weight after applying position caps. Futures are
omitted because front-month contract prices and rolls cannot be modeled as
ordinary adjusted ETF prices.

## Run without JupyterLab

The minimal workflow above covers tests and the robustness audit. The notebook
uses the same `trading.strategy` and `trading.backtest` functions and displays
the complete report and charts.

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
before running the backtest. Historical S&P 500 membership is filtered using
dated public snapshots, but Yahoo may not return all past securities, failed
ETFs/equities, ticker changes, or observed delisting returns. Five trailing
missing observations are treated as a total-loss liquidation, a conservative
placeholder rather than an observed delisting return. Interior gaps are
forward-filled and can hide stale pricing.

## Data sources and survivorship controls

The project uses free Yahoo Finance history through `yfinance`; it does not
use a paid market-data database. The interface is unofficial, may throttle
large requests, and does not guarantee delisted-security coverage or stable
adjusted history.

The current S&P 500 list is fetched from Wikipedia during a Yahoo refresh. The
strategy also downloads public historical snapshots from
[thuningxu/sp500nq100](https://github.com/thuningxu/sp500nq100), which currently
cover January 1996 through June 2, 2026. It carries the latest historical
state forward. The current roster is applied only on the current date when a
Yahoo price bar exists for that date; membership changes in the gap are not
reconstructed exactly. This keeps today's names out of earlier ranking
dates for the covered history. The community data has stated reconstruction
gaps, and Yahoo still omits some dead securities, delisting returns, ticker
identity changes, and complete corporate actions. This is a free research
approximation, not a complete survivorship-controlled database.

Other sources have narrower purposes:

- SEC EDGAR submissions/XBRL: company metadata and filings, not equity prices
  or membership history. Filing dates must be used to avoid hindsight.
- Stooq and public exchange archives: some old symbols may be available, but
  coverage, corporate actions, and usage rights vary.
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

The Alpha Vantage downloader uses the free API key only in an environment
variable. Get a key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key),
then set it for the current terminal session.

```sh
# macOS / Linux (zsh or bash)
export ALPHAVANTAGE_API_KEY="paste-your-key-here"

# Windows PowerShell
$env:ALPHAVANTAGE_API_KEY = "paste-your-key-here"
```

Do not put the key in Python code, a notebook, the ticker CSV, or a command-line
argument. To fetch a regular ticker, make a text file with one symbol per line:

```text
AAPL
MSFT
SPY
```

Then run:

```sh
PYTHONPATH=src .venv/bin/python scripts/download_alpha_vantage_history.py \
  --tickers-file data/alpha_tickers.txt
```

On Windows, run the same script with the project environment path:

```powershell
.\.venv\Scripts\python.exe scripts\download_alpha_vantage_history.py `
  --tickers-file data\alpha_tickers.txt
```

For aliases or known delisted symbols, use a CSV. `api_symbol` is the symbol
sent to Alpha Vantage; `symbol` is preserved as the local identity. Check
aliases carefully so a recycled ticker is not assigned to the wrong company.

```csv
symbol,api_symbol,status
AAPL,AAPL,active
SIVB,SIVB,delisted
OLD,NEW,delisted
```

The downloader stores one CSV per ticker immediately, a combined
`alpha_vantage_adjusted_history.csv`, request timestamps, and
`error_log.txt` under `data/alpha_vantage/`. A rerun validates and skips cached
tickers, then continues with missing or failed ones. It enforces at most five
requests in any rolling minute and a conservative 25 requests per rolling day;
the request ledger persists this limit between runs. Rate-limit messages get
exponential backoff. When the daily allowance is exhausted, remaining symbols
are deferred for a later run. Alpha Vantage currently documents a 25-request
free daily allowance and identifies `TIME_SERIES_DAILY_ADJUSTED` as a premium
endpoint, so a free key may be refused access to adjusted daily prices. The
[official quota page](https://www.alphavantage.co/support/) and
[API documentation](https://www.alphavantage.co/documentation/) describe these
limits and endpoint access. The script logs an access error rather than
repeatedly retrying every symbol.

Alpha Vantage uses `TIME_SERIES_DAILY_ADJUSTED&symbol=...` for price history.
Its separate `LISTING_STATUS` endpoint accepts `state=delisted` and an optional
`date`; for CSV rows marked `delisted`, the downloader queries and caches that
status list before fetching prices. The price endpoint itself has no
`state=delisted` parameter. It still attempts the supplied `api_symbol` and
logs empty or unsupported histories. The listing-status list is a roster
snapshot, not historical prices or complete company-identity history. See the
[official API documentation](https://www.alphavantage.co/documentation/#listing-status).

The optional FRED and SEC adapters are in
[src/trading/open_data.py](./src/trading/open_data.py). For Alpha Vantage, you
can also merge selected cached histories into the Yahoo panel with:

```sh
# Optional: merge selected Alpha Vantage histories into the Yahoo cache.
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
price files; this project's Yahoo Finance Parquet files are not automatically
valid LEAN data.

Run the pandas provenance audit before comparing engines:

```sh
PYTHONPATH=src .venv/bin/python scripts/provenance_audit.py
```

Performance figures from earlier versions are not comparable: portfolio
accounting, execution-date costs, universe, and ML validation have changed.
Regenerate results from the current cache and configuration before citing
them. Treat all risk profiles as exploratory choices, not an out-of-sample
ranking; select parameters on training data and report untouched test-period
performance.

The public membership mask improves point-in-time eligibility, but Yahoo still
lacks stable security identifiers and complete delisting returns. Adding names
to `historical_symbols` alone cannot correct those remaining gaps.

## Project defaults

- Historical start date: `2012-01-01`
- Signals and rebalancing: weekly
- Direction: long-only (`direction: long_only`)
- Initial capital: `$100,000`
- Position cap: `10%`
- Maximum equity exposure: `100%`
- Costs: commission, half-spread, slippage, and market impact
- Signal execution: next session close (`1` trading-day lag); with daily close
  data, close-to-close returns begin after the fill
- Drawdown control: exposure reduces progressively after `10%` drawdown and
  reaches the defensive floor at `25%`
- Forecast horizon: `21` trading days
- Volatility target: `20%` annualized
- Optional ML comparison: a lagged-feature linear regression model evaluated
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

## Interpreting results

Historical return tables from earlier revisions are intentionally removed:
they used different execution accounting and universes and should not be
quoted as current results. Use segmented/regime results, look-ahead mutation
checks, cost sensitivity, and buy-and-hold comparisons. A return increase in
one period is not validated by reproduction alone; inspect concentration,
turnover, selected symbols, and untouched out-of-sample periods. See
[RESEARCH_MATHEMATICS.md](./RESEARCH_MATHEMATICS.md) for assumptions and
[AUDIT_FINDINGS.md](./AUDIT_FINDINGS.md) for remaining data/accounting limits.

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
