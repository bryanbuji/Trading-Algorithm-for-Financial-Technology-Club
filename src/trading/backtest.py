
from typing import Optional

import numpy as np
import pandas as pd

TRADE_COLUMNS = [
    "date",
    "symbol",
    "side",
    "weight_before",
    "weight_after",
    "weight_change",
    "execution_price",
    "notional",
    "estimated_cost",
    "realized_profit_loss",
    "net_profit_loss",
    "profit_loss_pct",
    "cumulative_net_profit_loss",
    "cash_flow",
    "cumulative_cash_flow",
]


def run_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    initial_capital: float,
    commission_bps: float,
    half_spread_bps: float,
    slippage_bps: float,
    market_impact_bps: float,
    liquidate_trailing_missing: bool = True,
    trailing_missing_days: int = 5,
    execution_lag_days: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if execution_lag_days < 0:
        raise ValueError("execution_lag_days must be non-negative")
    if trailing_missing_days < 1:
        raise ValueError("trailing_missing_days must be at least 1")
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be a finite positive value")
    cost_inputs = (commission_bps, half_spread_bps, slippage_bps, market_impact_bps)
    if any(not np.isfinite(value) or value < 0 for value in cost_inputs):
        raise ValueError("transaction costs must be finite non-negative basis points")
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError("prices must have a unique, increasing date index")
    if target_weights.index.has_duplicates or not target_weights.index.is_monotonic_increasing:
        raise ValueError("target weights must have a unique, increasing date index")
    returns = prices.ffill().pct_change(fill_method=None).fillna(0)
    # Keep off-calendar signal labels (for example, Friday when the exchange
    # closed) so the signal carries to the next actual price date.
    signal_calendar = prices.index.union(target_weights.index).sort_values()
    weights = (
        target_weights.reindex(signal_calendar)
        .ffill()
        .reindex(prices.index)
        .fillna(0)
    )
    weights = weights.reindex(columns=prices.columns, fill_value=0)
    if not np.isfinite(weights.to_numpy()).all():
        raise ValueError("target weights must be finite")
    if (weights < -1e-12).any().any():
        raise ValueError("long-only target weights cannot be negative")
    if (weights.sum(axis=1) > 1.0 + 1e-9).any():
        raise ValueError("long-only target weights cannot exceed 100% exposure")
    liquidation_dates = {}
    if liquidate_trailing_missing:
        for symbol in prices.columns:
            valid_dates = prices[symbol].dropna().index
            if valid_dates.empty:
                weights[symbol] = 0.0
                continue
            last_valid = valid_dates[-1]
            trailing = prices.index > last_valid
            if trailing.sum() >= trailing_missing_days:
                # Decide only after the missing run reaches its threshold; do
                # not use later missing dates to backdate a delisting exit.
                liquidation_date = prices.index[trailing][trailing_missing_days - 1]
                returns.loc[liquidation_date, symbol] = -1.0
                weights.loc[weights.index >= liquidation_date, symbol] = 0.0
                liquidation_dates[symbol] = liquidation_date
    # Signals are filled at the configured next-session close. A close-to-close
    # return is earned only after that fill, and transaction costs are charged
    # on the fill date rather than the earlier signal date.
    holdings = weights.shift(execution_lag_days).fillna(0)
    for symbol, liquidation_date in liquidation_dates.items():
        holdings.loc[holdings.index >= liquidation_date, symbol] = 0.0
    turnover = holdings.diff().abs().sum(axis=1).fillna(holdings.abs().sum(axis=1))
    cost_rate = (commission_bps + half_spread_bps + slippage_bps + market_impact_bps) / 10000
    gross_returns = (holdings.shift(1).fillna(0) * returns).sum(axis=1)
    # A fully invested long-only account may lose all its capital, but cannot
    # owe more than its account value. This also covers a -100% delisting loss
    # plus execution costs on the forced liquidation.
    net_returns = (gross_returns - turnover * cost_rate).clip(lower=-1.0)
    equity = initial_capital * (1 + net_returns).cumprod()
    ledger = pd.DataFrame({"returns": net_returns, "turnover": turnover, "equity": equity})
    trades = build_trade_ledger(prices, holdings, equity, cost_rate, initial_capital)
    return ledger, holdings, trades


def buy_and_hold_backtest(
    prices: pd.DataFrame,
    symbol: str,
    initial_capital: float,
    commission_bps: float = 0.0,
    half_spread_bps: float = 0.0,
    slippage_bps: float = 0.0,
    market_impact_bps: float = 0.0,
) -> pd.DataFrame:
    """Backtest a fully invested, buy-and-hold position with entry costs."""
    if symbol not in prices:
        raise KeyError(f"Benchmark {symbol!r} is missing from prices")
    series = prices[symbol].dropna()
    if series.empty:
        raise ValueError(f"Benchmark {symbol!r} has no usable prices")
    returns = series.pct_change(fill_method=None).fillna(0.0)
    cost_rate = (
        commission_bps + half_spread_bps + slippage_bps + market_impact_bps
    ) / 10000
    returns.iloc[0] -= cost_rate
    equity = initial_capital * (1 + returns).cumprod()
    return pd.DataFrame(
        {
            "returns": returns,
            "turnover": pd.Series(0.0, index=series.index).mask(
                lambda values: values.index == series.index[0], 1.0
            ),
            "equity": equity,
        }
    )


def build_trade_ledger(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    equity: pd.Series,
    cost_rate: float,
    initial_capital: float,
) -> pd.DataFrame:
    changes = weights.diff().fillna(weights)
    records = []
    position_quantity = {}
    average_cost = {}
    cumulative_profit_loss = 0.0
    cumulative_cash_flow = 0.0
    for date, row in changes.iterrows():
        for symbol, weight_change in row[row.abs() > 1e-12].items():
            weight_after = float(weights.loc[date, symbol])
            portfolio_value = float(
                equity.shift(1).reindex([date]).fillna(initial_capital).iloc[0]
            )
            notional = abs(float(weight_change)) * portfolio_value
            raw_price = prices.loc[date, symbol]
            execution_price = float(raw_price) if pd.notna(raw_price) else 0.0
            quantity_price = (
                float(raw_price)
                if pd.notna(raw_price)
                else float(prices[symbol].loc[:date].ffill().iloc[-1])
            )
            quantity = notional / quantity_price
            realized_profit_loss = 0.0
            if weight_change > 0:
                previous_quantity = position_quantity.get(symbol, 0.0)
                previous_cost = average_cost.get(symbol, 0.0)
                position_quantity[symbol] = previous_quantity + quantity
                average_cost[symbol] = (
                    (previous_quantity * previous_cost) + (quantity * quantity_price)
                ) / position_quantity[symbol]
            else:
                realized_quantity = min(quantity, position_quantity.get(symbol, 0.0))
                realized_profit_loss = realized_quantity * (
                    execution_price - average_cost.get(symbol, quantity_price)
                )
                position_quantity[symbol] = max(position_quantity.get(symbol, 0.0) - quantity, 0.0)
                if position_quantity[symbol] == 0:
                    average_cost.pop(symbol, None)
            transaction_cost = notional * cost_rate
            net_profit_loss = realized_profit_loss - transaction_cost
            cash_flow = (
                quantity * execution_price - transaction_cost
                if weight_change < 0
                else -(quantity * quantity_price + transaction_cost)
            )
            cumulative_profit_loss += net_profit_loss
            cumulative_cash_flow += cash_flow
            records.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "side": "BUY" if weight_change > 0 else "SELL",
                    "weight_before": float(weight_after - weight_change),
                    "weight_after": weight_after,
                    "weight_change": float(weight_change),
                    "execution_price": execution_price,
                    "notional": notional,
                    "estimated_cost": transaction_cost,
                    "realized_profit_loss": realized_profit_loss,
                    "net_profit_loss": net_profit_loss,
                    "profit_loss_pct": net_profit_loss / notional if notional else 0.0,
                    "cumulative_net_profit_loss": cumulative_profit_loss,
                    "cash_flow": cash_flow,
                    "cumulative_cash_flow": cumulative_cash_flow,
                }
            )
    return pd.DataFrame.from_records(records, columns=TRADE_COLUMNS)


def plot_backtest_periods(
    ledger: pd.DataFrame,
    benchmark_prices: Optional[pd.Series] = None,
    periods: tuple[int, ...] = (1, 3, 5),
):
    import matplotlib.pyplot as plt

    period_labels = [f"{years}Y" for years in periods] + ["Full history"]
    figure, axes = plt.subplots(2, 2, figsize=(15, 10))
    for axis, years, label in zip(axes.flat, periods + (None,), period_labels):
        start = ledger.index[-1] - pd.DateOffset(years=years) if years else ledger.index[0]
        window = ledger.loc[ledger.index >= start, "equity"]
        axis.plot(window.index, window / window.iloc[0], label="Strategy", linewidth=2)
        if benchmark_prices is not None:
            benchmark = benchmark_prices.reindex(window.index).ffill().dropna()
            benchmark = benchmark / benchmark.iloc[0]
            axis.plot(benchmark.index, benchmark, label="Benchmark", alpha=0.75)
        axis.set_title(f"{label}: normalized growth")
        axis.set_ylabel("Growth (start = 1.000)")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle("Strategy performance over shorter time windows", fontsize=14)
    figure.tight_layout()
    return figure, axes


def plot_backtest(
    ledger: pd.DataFrame,
    trades: pd.DataFrame,
    benchmark_prices: Optional[pd.Series] = None,
):
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(
        3, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]}
    )
    equity = ledger["equity"]
    axes[0].plot(equity.index, equity, label="Strategy", linewidth=2)
    if benchmark_prices is not None:
        benchmark = benchmark_prices.reindex(equity.index).ffill().dropna()
        benchmark = benchmark / benchmark.iloc[0] * equity.iloc[0]
        axes[0].plot(benchmark.index, benchmark, label="Benchmark", alpha=0.75)
    if not trades.empty:
        trade_dates = trades.groupby("date")["side"].first()
        buy_dates = trade_dates[trade_dates == "BUY"].index
        sell_dates = trade_dates[trade_dates == "SELL"].index
        axes[0].scatter(buy_dates, equity.reindex(buy_dates), marker="^", color="green", label="Buy", zorder=3)
        axes[0].scatter(sell_dates, equity.reindex(sell_dates), marker="v", color="red", label="Sell", zorder=3)
    axes[0].set_title("Portfolio value over time")
    axes[0].set_ylabel("Portfolio value ($)")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    drawdown = equity / equity.cummax() - 1
    axes[1].fill_between(drawdown.index, drawdown * 100, 0, color="firebrick", alpha=0.3)
    axes[1].plot(drawdown.index, drawdown * 100, color="firebrick")
    axes[1].set_title("Portfolio drawdown")
    axes[1].set_ylabel("Drawdown (%)")
    axes[1].grid(alpha=0.25)

    if not trades.empty:
        activity = trades.assign(
            buys=trades["side"].eq("BUY").astype(int),
            sells=trades["side"].eq("SELL").astype(int),
        ).groupby("date")[["buys", "sells", "notional"]].sum()
        axes[2].bar(activity.index, activity["buys"], label="Buys", color="green", alpha=0.7)
        axes[2].bar(activity.index, -activity["sells"], label="Sells", color="red", alpha=0.7)
        axes[2].set_title("Trade activity (each bar represents one executed position change)")
        axes[2].set_ylabel("Trade count")
        axes[2].legend()
    axes[2].grid(alpha=0.25)
    figure.tight_layout()
    return figure, axes


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
