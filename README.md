# Trading research

Weekly, long-only equity/ETF research beginning on 2012-01-01. The initial
strategy combines cross-sectional momentum with a broad-market trend regime:
the portfolio selects the strongest assets, scales weights by volatility, and
reduces exposure during benchmark drawdowns. The configuration and interfaces
are intentionally direction-agnostic so long/short extensions can be added
without changing the data or backtest layers.

## Setup

```sh
cd trading-research
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m ipykernel install --user --name trading-research --display-name "Python (trading-research)"
```

## Run the research workflow

```sh
jupyter lab
```

Run notebooks in numeric order. `01_data_download.ipynb` downloads adjusted
daily data from Yahoo Finance and writes Parquet files under `data/processed`.
The remaining notebooks use those cached files. Yahoo Finance data is suitable
for research and is subject to its terms and limitations; use a licensed
provider before production trading.

The current S&P 500 list is downloaded when the data notebook runs. This gives
at least 250 symbols but introduces survivorship bias for historical studies;
use point-in-time constituent data for production-quality research.

## Defaults

- Universe: current S&P 500 constituents plus SPY and QQQ (505 symbols)
- Benchmarks: SPY and QQQ
- Signals: daily indicators sampled and executed weekly
- Direction: long-only (`direction: long_only`)
- Initial capital: $100,000
- Position cap: 10%; maximum equity exposure: 100%
- Costs: commission, half-spread, slippage, and market impact
- Drawdown control: exposure reduces progressively after 10% drawdown and
  reaches the configured floor at 25%

This is research software, not investment advice. Backtests can be wrong due
to survivorship bias, data errors, liquidity constraints, and model overfitting.
