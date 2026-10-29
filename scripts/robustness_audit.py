"""Run segmented, regime, benchmark, leakage, and cost diagnostics."""

import sys
from pathlib import Path

import pandas as pd

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from trading.backtest import buy_and_hold_backtest, performance_metrics, run_backtest
from trading.config import load_config
from trading.data import load_prices
from trading.robustness import (
    DEFAULT_REGIMES,
    assert_no_lookahead,
    return_concentration,
    segmented_performance,
    test_cost_sensitivity,
)
from trading.strategy import weekly_momentum_weights

config = load_config(root / "config.yaml")
prices = load_prices(root / "data" / "processed" / "prices.parquet")
trade_asset_classes = set(
    config.values.get("trade_asset_classes", config.values.get("asset_classes", {}))
)
excluded_symbols = [
    symbol
    for asset_class, symbols in config.values.get("asset_classes", {}).items()
    if asset_class not in trade_asset_classes
    for symbol in symbols
]

builder = lambda frame, benchmark: weekly_momentum_weights(
    frame,
    benchmark,
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
    excluded_symbols=excluded_symbols,
    benchmark_fallback=config.values.get("benchmark_fallback", False),
    rebalance_frequency=config["frequency"],
)

weights = builder(prices, config["benchmark"])
ledger, _, _ = run_backtest(
    prices,
    weights,
    config["initial_capital"],
    config["commission_bps"],
    config["half_spread_bps"],
    config["slippage_bps"],
    config["market_impact_bps"],
    execution_lag_days=config["signal_execution_lag_days"],
)
benchmark = buy_and_hold_backtest(
    prices,
    config["benchmark"],
    config["initial_capital"],
    config["commission_bps"],
    config["half_spread_bps"],
    config["slippage_bps"],
    config["market_impact_bps"],
)

assert_no_lookahead(prices, builder, config["benchmark"], "2020-01-01")
print("LOOK-AHEAD TEST: PASS")
print("\nSEGMENTED PERFORMANCE")
print(segmented_performance(ledger).round(4).to_string())
print("\nBULL/BEAR PERFORMANCE")
print(segmented_performance(ledger, DEFAULT_REGIMES).round(4).to_string())
print("\nSTRATEGY VS BUY-AND-HOLD")
comparison = {
    "strategy": performance_metrics(ledger),
    f"buy_and_hold_{config['benchmark']}": performance_metrics(benchmark),
}
nasdaq = config["nasdaq_benchmark"]
if nasdaq in prices:
    comparison[f"buy_and_hold_{nasdaq}"] = performance_metrics(
        buy_and_hold_backtest(
            prices,
            nasdaq,
            config["initial_capital"],
            config["commission_bps"],
            config["half_spread_bps"],
            config["slippage_bps"],
            config["market_impact_bps"],
        )
    )
print(pd.DataFrame(comparison).round(4).to_string())
print(f"\nPositive-return concentration after 2022: {return_concentration(ledger):.3%}")
scenarios = [
    {
        "name": "baseline",
        "commission_bps": config["commission_bps"],
        "half_spread_bps": config["half_spread_bps"],
        "slippage_bps": config["slippage_bps"],
        "market_impact_bps": config["market_impact_bps"],
    },
    {
        "name": "high_cost",
        "commission_bps": 5.0,
        "half_spread_bps": 10.0,
        "slippage_bps": 20.0,
        "market_impact_bps": 10.0,
    },
]
print("\nCOST SENSITIVITY")
print(
    test_cost_sensitivity(
        prices,
        weights,
        config["initial_capital"],
        scenarios,
        execution_lag_days=config["signal_execution_lag_days"],
    ).round(4).to_string()
)
