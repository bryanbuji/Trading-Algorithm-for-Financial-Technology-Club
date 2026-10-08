# Machine Learning Trade Model

This optional workflow evaluates a regularized Ridge model against the shared
weekly backtesting infrastructure. It uses lagged momentum, volatility,
relative-strength, and benchmark-volatility features and trains
chronologically to avoid look-ahead leakage.

## Setup

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -r "Machine Learning Trade Model/requirements.txt"
```

The ML workflow uses the parent project's cached prices. Download them first
with `notebooks/01_data_download.ipynb`.

## Run

From the repository root:

```sh
PYTHONPATH=src:"Machine Learning Trade Model/src" \
  .venv/bin/python "Machine Learning Trade Model/scripts/run_ml_model.py"
```

Or start JupyterLab and open
`Machine Learning Trade Model/notebooks/ml_trade_model.ipynb`. The notebook
locates the parent project automatically and displays model quality,
performance, risk, trade, and period-return charts.

The model is for educational research only. Its out-of-sample correlation is
not evidence that future returns are predictable, and the shared dataset uses
current S&P 500 constituents across history, which introduces survivorship
bias.
