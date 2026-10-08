import numpy as np
import pandas as pd
from typing import Optional


def weekly_momentum_weights(
    prices: pd.DataFrame,
    benchmark: str,
    top_n: int = 10,
    lookback_days: int = 126,
    skip_days: int = 21,
    volatility_days: int = 63,
    max_position_weight: float = 0.10,
    max_equity_exposure: float = 1.0,
    defensive_exposure: float = 0.25,
    stop_loss_pct: float = 0.15,
    drawdown_start: float = 0.10,
    drawdown_full_defense: float = 0.25,
    expected_returns: Optional[pd.DataFrame] = None,
    volatility_target: Optional[float] = None,
) -> pd.DataFrame:
    if benchmark not in prices:
        raise KeyError(f"Benchmark {benchmark!r} is missing from prices")
    weekly = prices.resample("W-FRI").last().ffill()
    daily_returns = prices.pct_change(fill_method=None)
    momentum = prices.shift(skip_days).div(prices.shift(lookback_days)).sub(1)
    volatility = daily_returns.rolling(volatility_days).std() * np.sqrt(252)
    momentum = momentum.reindex(weekly.index, method="ffill")
    volatility = volatility.reindex(weekly.index, method="ffill")
    trailing_high = prices.rolling(volatility_days).max().reindex(weekly.index, method="ffill")
    stop_triggered = weekly < trailing_high * (1 - stop_loss_pct)
    benchmark_drawdown = weekly[benchmark].div(weekly[benchmark].cummax()).sub(1).abs()
    exposure = 1 - (benchmark_drawdown - drawdown_start).clip(lower=0) / max(
        drawdown_full_defense - drawdown_start, np.finfo(float).eps
    )
    exposure = exposure.clip(lower=defensive_exposure, upper=1.0)
    weights = pd.DataFrame(0.0, index=weekly.index, columns=prices.columns)
    candidates = [symbol for symbol in prices.columns if symbol != benchmark]
    for date in weekly.index:
        scores = (
            expected_returns.reindex(index=weekly.index, columns=candidates, method="ffill")
            .loc[date]
            .dropna()
            if expected_returns is not None
            else momentum.loc[date, candidates].dropna()
        )
        scores = scores[~stop_triggered.loc[date, scores.index]]
        vol = volatility.loc[date, candidates].reindex(scores.index)
        scores = scores[vol.notna() & (vol > 0)].nlargest(top_n)
        if scores.empty:
            continue
        raw = (1 / vol.loc[scores.index]).replace([np.inf, -np.inf], np.nan).dropna()
        raw = raw / raw.sum() * min(max_equity_exposure, exposure.loc[date])
        weights.loc[date, raw.index] = raw.clip(upper=max_position_weight)
        total = weights.loc[date].sum()
        if total > max_equity_exposure:
            weights.loc[date] *= max_equity_exposure / total
        if volatility_target is not None and total > 0:
            selected_returns = daily_returns[weights.columns[weights.loc[date] > 0]]
            portfolio_volatility = selected_returns.mul(weights.loc[date], axis=1).sum(axis=1).rolling(
                volatility_days
            ).std().iloc[-1] * np.sqrt(252)
            if pd.notna(portfolio_volatility) and portfolio_volatility > volatility_target:
                weights.loc[date] *= volatility_target / portfolio_volatility
    return weights
