# Trading Algorithm for Financial Technology Club

This project is a weekly, long-only equity/ETF research system. It combines
cross-sectional momentum, volatility-adjusted position sizing, a broad-market
trend regime, trailing stop-loss filtering, transaction costs, and drawdown
exposure controls. It is designed for teaching and reproducible research; it
does not place live brokerage orders.

## Requirements

- macOS, Linux, or Windows
- Python 3.9 or newer
- Internet access for Yahoo Finance data downloads

Check your Python installation:

```sh
python3 --version
```

## One-time setup

Run these commands from Terminal after cloning the repository:

```sh
git clone <repository-url>
cd Trading-Algorithm-for-Financial-Technology-Club
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m ipykernel install --user \
  --name trading-research \
  --display-name "Python (trading-research)"
```

If `.venv` already exists, skip the `python3 -m venv .venv` command. The
virtual environment is intentionally excluded from Git and must be created
locally on each computer.

## Start JupyterLab

With the virtual environment activated:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club
source .venv/bin/activate
jupyter lab
```

If your shell says `jupyter: command not found`, bypass shell `PATH`
configuration and run:

```sh
.venv/bin/python -m jupyterlab
```

JupyterLab opens in a browser at a localhost URL. In JupyterLab:

1. Open `notebooks/01_data_download.ipynb`.
2. Select the `Python (trading-research)` kernel.
3. Choose **Kernel → Restart Kernel and Run All Cells**.
4. Confirm that it reports approximately `3,700 dates x 505 symbols`.
5. Open `notebooks/02_backtest_baseline.ipynb`.
6. Choose **Kernel → Restart Kernel and Run All Cells**.

The first notebook downloads adjusted daily prices and saves them to
`data/processed/prices.parquet`. The second notebook uses that cached data and
prints a formatted performance report.

## Run without JupyterLab

This command runs the test suite:

```sh
cd Trading-Algorithm-for-Financial-Technology-Club
PYTHONPATH=src .venv/bin/python -m pytest -q tests
```

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
ledger, holdings = run_backtest(
    prices,
    weights,
    config["initial_capital"],
    config["commission_bps"],
    config["half_spread_bps"],
    config["slippage_bps"],
    config["market_impact_bps"],
)
print(format_performance_report(ledger, config["initial_capital"]))
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

After changing `symbols`, run `01_data_download.ipynb` again before running
the backtest. The default universe is the current S&P 500 constituents plus
`SPY` and `QQQ` (505 symbols). Because current constituents are used for the
whole historical period, this dataset has survivorship bias. Point-in-time
constituent data is required for production-quality research.

## Project defaults

- Historical start date: `2012-01-01`
- Signals and rebalancing: weekly
- Direction: long-only (`direction: long_only`)
- Initial capital: `$100,000`
- Position cap: `10%`
- Maximum equity exposure: `100%`
- Costs: commission, half-spread, slippage, and market impact
- Drawdown control: exposure reduces progressively after `10%` drawdown and
  reaches the defensive floor at `25%`

## Troubleshooting

### `python: command not found`

Use `python3` rather than `python`.

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

## Important limitations

This is not investment advice and is not a live trading system. Backtests can
be wrong because of survivorship bias, data errors, stale prices, liquidity
constraints, execution assumptions, and model overfitting. Review results
with walk-forward and out-of-sample validation before considering paper
trading.
