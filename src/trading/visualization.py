from typing import Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd


def select_period(
    frame: pd.DataFrame,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    selected = frame
    if start is not None:
        selected = selected.loc[selected.index >= pd.Timestamp(start)]
    if end is not None:
        selected = selected.loc[selected.index <= pd.Timestamp(end)]
    return selected


def period_returns(ledger: pd.DataFrame, frequency: str = "Y") -> pd.Series:
    frequency = {"Y": "YE", "M": "ME", "5Y": "5YE"}.get(frequency, frequency)
    return ledger["equity"].resample(frequency).last().pct_change().dropna()


def plot_diagnostics(
    ledger: pd.DataFrame,
    trades: pd.DataFrame,
    portfolio_risk: pd.DataFrame,
    benchmark_prices: Optional[pd.Series] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[plt.Figure, "object"]:
    selected_ledger = select_period(ledger, start, end)
    selected_risk = select_period(portfolio_risk, start, end)
    selected_trades = trades.copy()
    if not selected_trades.empty:
        selected_trades["date"] = pd.to_datetime(selected_trades["date"])
        selected_trades = selected_trades.set_index("date")
        selected_trades = select_period(selected_trades, start, end)
    figure, axes = plt.subplots(4, 2, figsize=(16, 18))
    axes = axes.flatten()

    equity = selected_ledger["equity"]
    axes[0].plot(equity.index, equity, label="Strategy")
    if benchmark_prices is not None:
        benchmark = select_period(benchmark_prices.to_frame("benchmark"), start, end)["benchmark"]
        benchmark = benchmark / benchmark.iloc[0] * equity.iloc[0]
        axes[0].plot(benchmark.index, benchmark, label="Benchmark")
    axes[0].set_title("Equity curve")
    axes[0].set_ylabel("Portfolio value ($)")

    axes[1].plot(equity.index, equity / equity.iloc[0] - 1)
    axes[1].set_title("Cumulative return")
    axes[1].set_ylabel("Return (%)")
    axes[1].yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")

    drawdown = equity / equity.cummax() - 1
    axes[2].fill_between(drawdown.index, drawdown, 0, color="firebrick", alpha=0.3)
    axes[2].set_title("Drawdown")
    axes[2].yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")

    if not selected_trades.empty:
        counts = selected_trades.groupby(pd.Grouper(freq="ME")).size()
        notional = selected_trades.groupby(pd.Grouper(freq="ME"))["notional"].sum()
        pnl = selected_trades.groupby(pd.Grouper(freq="ME"))["net_profit_loss"].sum()
    else:
        counts = notional = pnl = pd.Series(dtype=float)
    axes[3].bar(counts.index, counts.values, color="steelblue")
    axes[3].set_title("Monthly trade count")
    axes[3].set_ylabel("Trades")

    axes[4].bar(notional.index, notional.values, color="darkorange")
    axes[4].set_title("Monthly traded notional")
    axes[4].set_ylabel("Notional ($)")

    axes[5].bar(pnl.index, pnl.values, color=["green" if x >= 0 else "red" for x in pnl.values])
    axes[5].set_title("Monthly net profit/loss")
    axes[5].set_ylabel("Net P/L ($)")

    if "portfolio_volatility" in selected_risk:
        axes[6].plot(selected_risk.index, selected_risk["portfolio_volatility"], label="Volatility")
        axes[6].plot(selected_risk.index, selected_risk["portfolio_sharpe"], label="Sharpe")
    axes[6].set_title("Rolling portfolio risk")
    axes[6].legend()

    axes[7].plot(selected_risk.index, selected_risk["exposure"], label="Exposure")
    axes[7].plot(selected_risk.index, selected_risk["positions"], label="Positions")
    axes[7].set_title("Exposure and position count")
    axes[7].legend()

    for axis in axes:
        axis.grid(alpha=0.25)
        axis.tick_params(axis="x", rotation=30)
    figure.suptitle(f"Backtest diagnostics: {start or 'start'} to {end or 'end'}", fontsize=16)
    figure.tight_layout()
    return figure, axes


def plot_periodic_returns(
    ledger: pd.DataFrame,
    period: str = "Y",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[plt.Figure, "object"]:
    selected = select_period(ledger, start, end)
    returns = period_returns(selected, period)
    figure, axis = plt.subplots(figsize=(14, 5))
    colors = ["green" if value >= 0 else "red" for value in returns]
    axis.bar(returns.index.astype(str), returns * 100, color=colors)
    axis.set_title(f"{'Annual' if period == 'Y' else 'Monthly' if period == 'M' else 'Five-year' if period == '5Y' else 'Periodic'} returns")
    axis.set_ylabel("Return (%)")
    axis.tick_params(axis="x", rotation=45)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    return figure, axis
