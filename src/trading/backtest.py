import pandas as pd


def run_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    initial_capital: float,
    commission_bps: float,
    half_spread_bps: float,
    slippage_bps: float,
    market_impact_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    returns = prices.pct_change().fillna(0)
    weights = target_weights.reindex(prices.index).ffill().fillna(0)
    weights = weights.reindex(columns=prices.columns, fill_value=0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    cost_rate = (commission_bps + half_spread_bps + slippage_bps + market_impact_bps) / 10000
    net_returns = (weights.shift(1).fillna(0) * returns).sum(axis=1) - turnover * cost_rate
    equity = initial_capital * (1 + net_returns).cumprod()
    ledger = pd.DataFrame({"returns": net_returns, "turnover": turnover, "equity": equity})
    return ledger, weights


def performance_metrics(ledger: pd.DataFrame) -> pd.Series:
    returns = ledger["returns"]
    years = max((returns.index[-1] - returns.index[0]).days / 365.25, 1 / 365.25)
    drawdown = ledger["equity"] / ledger["equity"].cummax() - 1
    volatility = returns.std() * (252**0.5)
    return pd.Series(
        {
            "total_return": ledger["equity"].iloc[-1] / ledger["equity"].iloc[0] - 1,
            "annualized_return": (ledger["equity"].iloc[-1] / ledger["equity"].iloc[0]) ** (1 / years) - 1,
            "annualized_volatility": volatility,
            "sharpe": returns.mean() / returns.std() * (252**0.5) if returns.std() else float("nan"),
            "max_drawdown": drawdown.min(),
            "average_turnover": ledger["turnover"].mean(),
        }
    )


def format_performance_report(ledger: pd.DataFrame, initial_capital: float) -> str:
    """Return a readable, three-decimal performance summary."""
    metrics = performance_metrics(ledger)
    final_equity = float(ledger["equity"].iloc[-1])
    total_profit = final_equity - initial_capital

    return "\n".join(
        [
            "Backtest Performance",
            "--------------------",
            f"Initial capital:        ${initial_capital:,.3f}",
            f"Final portfolio value:  ${final_equity:,.3f}",
            f"Total profit:           ${total_profit:,.3f}",
            f"Total return:           {metrics['total_return'] * 100:.3f}%",
            f"Annualized return:      {metrics['annualized_return'] * 100:.3f}%",
            f"Annualized volatility:  {metrics['annualized_volatility'] * 100:.3f}%",
            f"Sharpe ratio:           {metrics['sharpe']:.3f}",
            f"Maximum drawdown:       {metrics['max_drawdown'] * 100:.3f}%",
            f"Average turnover:       {metrics['average_turnover'] * 100:.3f}%",
        ]
    )
