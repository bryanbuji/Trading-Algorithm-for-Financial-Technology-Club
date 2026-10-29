"""Robustness diagnostics for historical backtests."""

from collections.abc import Iterable, Mapping
from typing import Optional

import pandas as pd

from trading.backtest import performance_metrics

DEFAULT_PERIODS = {
    "2012-2016": ("2012-01-01", "2016-12-31"),
    "2016-2020": ("2016-01-01", "2020-12-31"),
    "2020-2023": ("2020-01-01", "2023-12-31"),
    "2023-2026": ("2023-01-01", "2026-12-31"),
}

DEFAULT_REGIMES = {
    "bull_2012_2015": ("2012-01-01", "2015-12-31"),
    "bear_covid": ("2020-02-19", "2020-03-23"),
    "bull_recovery": ("2020-03-24", "2021-12-31"),
    "bear_2022": ("2022-01-03", "2022-10-12"),
    "bull_2023_2026": ("2023-01-01", "2026-12-31"),
}


def _window(ledger: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    result = ledger.loc[pd.Timestamp(start) : pd.Timestamp(end)].copy()
    if result.empty:
        raise ValueError(f"No backtest observations in {start} through {end}")
    first_equity = result["equity"].iloc[0]
    result["equity"] = result["equity"] / first_equity
    return result


def segmented_performance(
    ledger: pd.DataFrame,
    periods: Optional[Mapping[str, tuple[str, str]]] = None,
) -> pd.DataFrame:
    """Measure independent calendar windows without hiding return concentration."""
    periods = periods or DEFAULT_PERIODS
    records = []
    for name, (start, end) in periods.items():
        window = _window(ledger, start, end)
        metrics = performance_metrics(window)
        records.append(
            {
                "period": name,
                "start": window.index.min(),
                "end": window.index.max(),
                "total_return": metrics["total_return"],
                "annualized_return": metrics["annualized_return"],
                "annualized_volatility": metrics["annualized_volatility"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "average_turnover": metrics["average_turnover"],
            }
        )
    return pd.DataFrame.from_records(records).set_index("period")


def return_concentration(ledger: pd.DataFrame, start: str = "2022-01-01") -> float:
    """Share of cumulative positive daily P/L generated after ``start``."""
    returns = ledger["returns"]
    positive = returns.clip(lower=0).sum()
    if positive <= 0:
        return float("nan")
    return float(returns.loc[start:].clip(lower=0).sum() / positive)


def assert_no_lookahead(
    prices: pd.DataFrame,
    weight_builder,
    benchmark: str,
    mutation_start: str,
) -> None:
    """Raise if future price mutations change signals before the mutation date."""
    baseline = weight_builder(prices, benchmark)
    mutated = prices.copy()
    future = mutated.index > pd.Timestamp(mutation_start)
    mutated.loc[future] = mutated.loc[future] * 17.0
    changed = baseline.loc[:mutation_start].compare(
        weight_builder(mutated, benchmark).loc[:mutation_start]
    )
    if not changed.empty:
        raise AssertionError(
            f"Future prices changed pre-{mutation_start} weights: {len(changed)} rows"
        )


def test_cost_sensitivity(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    initial_capital: float,
    cost_scenarios: Iterable[Mapping[str, float]],
    execution_lag_days: int = 1,
) -> pd.DataFrame:
    """Run the same signals under multiple explicit execution-cost assumptions."""
    from trading.backtest import run_backtest

    records = []
    for scenario in cost_scenarios:
        ledger, _, _ = run_backtest(
            prices,
            weights,
            initial_capital,
            scenario["commission_bps"],
            scenario["half_spread_bps"],
            scenario["slippage_bps"],
            scenario["market_impact_bps"],
            execution_lag_days=execution_lag_days,
        )
        metrics = performance_metrics(ledger)
        records.append(
            {
                "scenario": scenario["name"],
                "total_return": metrics["total_return"],
                "annualized_return": metrics["annualized_return"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "total_cost_bps": sum(
                    scenario[key]
                    for key in (
                        "commission_bps",
                        "half_spread_bps",
                        "slippage_bps",
                        "market_impact_bps",
                    )
                ),
            }
        )
    return pd.DataFrame.from_records(records).set_index("scenario")
