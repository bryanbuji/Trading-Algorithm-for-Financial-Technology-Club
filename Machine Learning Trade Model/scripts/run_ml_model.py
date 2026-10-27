"""Run the standalone machine-learning trading workflow."""

from pathlib import Path
import sys


def project_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if not (root / "src" / "trading").is_dir():
        raise RuntimeError("Could not locate the parent trading project.")
    return root


root = project_root()
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "Machine Learning Trade Model" / "src"))

from ml_trade_model.modeling import walk_forward_predictions
from trading.backtest import format_performance_report, run_backtest
from trading.config import load_config
from trading.data import load_prices
from trading.risk import portfolio_risk_diagnostics
from trading.strategy import weekly_momentum_weights


config = load_config(root / "config.yaml")
prices = load_prices(root / "data" / "processed" / "prices.parquet")
predictions, quality = walk_forward_predictions(
    prices, config["benchmark"], frequency=config["frequency"]
)
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
    expected_returns=predictions,
    volatility_target=config["volatility_target"],
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
    execution_lag_days=config["signal_execution_lag_days"],
)
print("ML MODEL QUALITY")
print(f"Out-of-sample observations: {quality['observations']:,.0f}")
print(f"Prediction/realized-return correlation: {quality['correlation']:.3f}")
print("ML-BIASED RANKING MODEL")
print(format_performance_report(ledger, config["initial_capital"]))
print(f"Trades recorded: {len(trades):,}")
print(portfolio_risk_diagnostics(holdings, prices, config["benchmark"]).tail(1))
