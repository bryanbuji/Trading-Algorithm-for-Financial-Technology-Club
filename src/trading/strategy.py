from typing import Optional

import numpy as np
import pandas as pd


def _allocate_capped_inverse_volatility(
    volatility: pd.Series,
    target_exposure: float,
    max_position_weight: float,
) -> pd.Series:
    """Allocate exposure while redistributing weight removed by caps."""
    remaining = volatility.dropna().loc[lambda values: values > 0].copy()
    allocation = pd.Series(0.0, index=remaining.index)
    remaining_exposure = target_exposure
    while not remaining.empty and remaining_exposure > 0:
        raw = (1 / remaining) / (1 / remaining).sum() * remaining_exposure
        capped = raw > max_position_weight
        if not capped.any():
            allocation.loc[raw.index] += raw
            break
        capped_symbols = raw.index[capped]
        allocation.loc[capped_symbols] = max_position_weight
        remaining_exposure -= max_position_weight * len(capped_symbols)
        remaining = remaining.drop(capped_symbols)
    return allocation[allocation > 0]


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
    excluded_symbols: Optional[list[str]] = None,
    include_benchmark: bool = False,
    benchmark_fallback: bool = False,
    rebalance_frequency: str = "W-FRI",
) -> pd.DataFrame:
    if benchmark not in prices:
        raise KeyError(f"Benchmark {benchmark!r} is missing from prices")
    if rebalance_frequency == "D":
        weekly = prices.ffill()
    else:
        weekly = prices.resample(rebalance_frequency).last().ffill()
    daily_returns = prices.pct_change(fill_method=None)
    momentum = prices.shift(skip_days).div(prices.shift(lookback_days)).sub(1)
    volatility = (
        daily_returns.rolling(
            volatility_days,
            min_periods=min(20, volatility_days),
        ).std()
        * np.sqrt(252)
    ).ffill()
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
    excluded = set(excluded_symbols or [])
    candidates = [
        symbol
        for symbol in prices.columns
        if (include_benchmark or symbol != benchmark) and symbol not in excluded
    ]
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
        target_exposure = min(max_equity_exposure, exposure.loc[date])
        raw = _allocate_capped_inverse_volatility(
            vol.loc[scores.index],
            target_exposure,
            max_position_weight,
        )
        if raw.empty and benchmark_fallback:
            weights.loc[date, benchmark] = min(max_equity_exposure, exposure.loc[date])
            continue
        weights.loc[date, raw.index] = raw
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
