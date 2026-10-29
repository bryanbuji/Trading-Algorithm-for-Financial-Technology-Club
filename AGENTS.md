# Repository Guidelines

## Project Structure & Module Organization

The core Python package is in `src/trading/`; it contains data access, strategy, backtesting, risk, robustness, configuration, and visualization code. `scripts/` holds data and audit utilities. The pytest suite is in `tests/`, and the research workflow is documented in `notebooks/`. `config.yaml` controls the experiment, while `data/` contains generated caches and is not committed. The optional ML comparison is a separate project under `Machine Learning Trade Model/`, with its own source, tests, notebook, README, and `requirements.txt`.

## Build, Test, and Development Commands

Use Python 3.15 as specified in the README. After installing `requirements.txt`, run commands from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests
PYTHONPATH=src .venv/bin/python scripts/robustness_audit.py
PYTHONPATH=src .venv/bin/python scripts/provenance_audit.py
.venv/bin/python -m jupyterlab
```

These run the core tests, check strategy robustness and data provenance, and launch the notebook environment. For the ML project, install its separate requirements and follow its README; avoid mixing its dependencies into the core environment.

## Coding Style & Naming Conventions

Follow the existing Python style: four-space indentation, `snake_case` for modules, functions, and variables, and `CapWords` for classes. Keep strategy and backtest logic in `src/trading/` rather than duplicating it in notebooks. Use descriptive names and focused functions; update configuration or documentation when behavior or defaults change. Ruff is among the project dependencies; there is no repository-wide formatter configuration, so match neighboring code.

## Testing Guidelines

Tests use pytest and are named `test_*.py`; test functions should use the `test_*` prefix. Add or update focused tests under `tests/` for core behavior changes. Run the full core suite with the command above. ML changes should also be tested from `Machine Learning Trade Model/tests/` using that project's environment and instructions.

## Commit & Pull Request Guidelines

Recent history uses short, descriptive subjects but has no consistent formal prefix. Write a concise imperative summary, such as `Fix capped portfolio weight redistribution`. Pull requests should explain the research or behavior change, note configuration and data assumptions, list validation commands and outcomes, and include screenshots for notebook or chart changes. Never commit API keys, local environments, or generated market-data caches.

## Research and Data Safety

This is a research backtester, not live execution software. Preserve realistic execution timing and transaction costs, avoid look-ahead leakage, and document data-source or survivorship-bias limitations when changing the universe or data pipeline. Keep credentials such as `ALPHAVANTAGE_API_KEY` and `SEC_USER_AGENT` in the local environment, not in source files or notebooks.
