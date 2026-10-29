# Machine Learning Trade Model

This optional workflow evaluates a linear regression model against the shared
backtesting infrastructure. It uses lagged momentum, volatility,
relative-strength, and benchmark-volatility features and trains
chronologically with a 21-observation purge so training labels do not reach
into each prediction date. This avoids one identified label-overlap leak, but
does not make the model or strategy robust to selection bias or tuning.

## Setup

From the repository root:

```sh
python3.15 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r "Machine Learning Trade Model/requirements.txt"
```

The ML workflow uses the parent project's cached prices. Download them first
with `notebooks/01_data_download.ipynb`. It follows the `frequency` value in
the parent `config.yaml`, so changing that value also changes ML feature
sampling and portfolio rebalancing.

## Run

From the repository root:

```sh
PYTHONPATH=src:"Machine Learning Trade Model/src" \
  .venv/bin/python "Machine Learning Trade Model/scripts/run_ml_model.py"
```

Or start JupyterLab and open
`Machine Learning Trade Model/notebooks/ml_trade_model.ipynb`. The notebook
locates the parent project automatically and displays model quality,
performance, risk, trade, and period-return charts. It saves the complete trade
ledger to ignored `data/processed/ml_trades.csv` and renders a formatted
100-row preview.

The target is a 21-bar future return at the configured frequency (21 weeks
when weekly, 21 sessions when daily). Prediction dates are sparse because the
model retrains every 13 bars; overlapping target windows make the reported
correlation descriptive, not a statistical significance test. The shared
price cache uses a selected ETF list, not point-in-time ETF membership or
complete delisted-security data, so survivorship bias remains.

See [LEARNING_METHOD.md](./LEARNING_METHOD.md) for the model type, features,
target, and walk-forward training method.
