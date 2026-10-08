import numpy as np
import pandas as pd


def risk_diagnostics(
    prices: pd.DataFrame,
    benchmark: str,
    forecast_horizon_days: int = 21,
    volatility_days: int = 63,
) -> dict[str, pd.DataFrame]:
    returns = prices.pct_change(fill_method=None)
    annualization = np.sqrt(252)
    volatility = returns.rolling(volatility_days).std() * annualization
    downside = returns.where(returns < 0).rolling(volatility_days).std() * annualization
    benchmark_returns = returns[benchmark]
    beta = returns.rolling(volatility_days).cov(benchmark_returns).div(
        benchmark_returns.rolling(volatility_days).var(), axis=0
    )
    correlation = returns.rolling(volatility_days).corr(benchmark_returns)
    momentum = prices.shift(21).div(prices.shift(126)).sub(1)
    expected_return = (momentum / np.sqrt(126 / 252)).clip(-1.0, 1.0)
    expected_profit = expected_return * forecast_horizon_days / 252
    expected_loss = (volatility * np.sqrt(forecast_horizon_days / 252)).clip(lower=1e-9)
    reward_risk = expected_profit.div(expected_loss).replace([np.inf, -np.inf], np.nan)
    sharpe = expected_profit.div(expected_loss).replace([np.inf, -np.inf], np.nan)
    return {
        "expected_return": expected_return,
        "volatility": volatility,
        "downside_volatility": downside,
        "beta": beta,
        "correlation": correlation,
        "expected_profit": expected_profit,
        "expected_loss": expected_loss,
        "reward_risk": reward_risk,
        "forecast_sharpe": sharpe,
    }


def portfolio_risk_diagnostics(
    holdings: pd.DataFrame,
    prices: pd.DataFrame,
    benchmark: str,
) -> pd.DataFrame:
    returns = prices.pct_change(fill_method=None)
    weekly_holdings = holdings.reindex(returns.index).ffill().fillna(0)
    portfolio_returns = (weekly_holdings.shift(1).fillna(0) * returns).sum(axis=1)
    rolling_volatility = portfolio_returns.rolling(63).std() * np.sqrt(252)
    drawdown = (1 + portfolio_returns).cumprod()
    drawdown = drawdown / drawdown.cummax() - 1
    return pd.DataFrame(
        {
            "exposure": weekly_holdings.sum(axis=1),
            "positions": (weekly_holdings > 0).sum(axis=1),
            "concentration_hhi": (weekly_holdings**2).sum(axis=1),
            "portfolio_volatility": rolling_volatility,
            "portfolio_sharpe": portfolio_returns.rolling(63).mean().div(
                portfolio_returns.rolling(63).std()
            ) * np.sqrt(252),
            "portfolio_drawdown": drawdown,
            "benchmark_return": returns[benchmark].rolling(63).sum(),
        }
    )
