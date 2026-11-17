"""Print provenance and timing facts for a cached backtest dataset."""

from pathlib import Path
import sys

import pandas as pd

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from trading.config import load_config
from trading.data import coverage_report, load_configured_market_data
from trading.strategy import weekly_momentum_weights

config = load_config(root / "config.yaml")
prices, universe_membership = load_configured_market_data(config, root)
coverage = coverage_report(prices)

print("DATA PROVENANCE")
print(f"Date range: {prices.index.min().date()} to {prices.index.max().date()}")
print(f"Symbols: {prices.shape[1]:,}")
print(f"Symbols with observations: {coverage['available'].sum():,}")
print(f"Benchmark: {config['benchmark']}")
print(f"Frequency: {config['frequency']}")
print(f"Configured signal lag: {config['signal_execution_lag_days']} trading day")
daily_returns = prices.pct_change(fill_method=None)
print(f"Duplicate dates: {int(prices.index.duplicated().sum()):,}")
print(f"Non-positive prices: {int((prices <= 0).sum().sum()):,}")
print(f"Maximum absolute daily return: {daily_returns.abs().max().max():.2%}")
print(
    "Trailing missing histories are liquidated at zero by the pandas backtest; "
    "temporary interior gaps are forward-filled for return calculation."
)
print("\nLATEST SYMBOL COVERAGE GAPS")
print(coverage.sort_values("last_date").head(20).to_string())

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
    volatility_target=config["volatility_target"],
    rebalance_frequency=config["frequency"],
    universe_membership=universe_membership,
)
rebalance_dates = weights.index[weights.diff().abs().sum(axis=1) > 0]
daily_rebalance_dates = prices.index.intersection(rebalance_dates)
print("\nSIGNAL TIMING")
print(f"Configured signal dates: {len(rebalance_dates):,}")
print(f"Signals coinciding with daily observations: {len(daily_rebalance_dates):,}")
print(
    "The pandas engine fills after the configured row lag and earns close-to-close "
    "returns only after the fill date."
)
