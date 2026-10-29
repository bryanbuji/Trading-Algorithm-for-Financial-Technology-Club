import pandas as pd

from trading.backtest import (
    buy_and_hold_backtest,
    format_performance_report,
    run_backtest,
)
from trading.risk import risk_diagnostics
from trading.robustness import assert_no_lookahead, segmented_performance
from trading.strategy import weekly_momentum_weights
from trading.visualization import period_returns, select_period


def test_performance_report_formats_profit_and_percentages() -> None:
    index = pd.date_range("2020-01-01", periods=2, freq="D")
    ledger = pd.DataFrame(
        {"returns": [0.0, 0.1], "turnover": [0.0, 0.2], "equity": [1000.0, 1100.0]},
        index=index,
    )

    report = format_performance_report(ledger, 1000.0)

    assert "Total profit:           $100.000" in report
    assert "Total return:           10.000%" in report
    assert "Average turnover:       10.000%" in report


def test_backtest_records_position_changes() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="D")
    prices = pd.DataFrame({"AAA": [10.0, 11.0, 12.0]}, index=index)
    target_weights = pd.DataFrame({"AAA": [0.5, 0.0, 0.25]}, index=index)

    _, _, trades = run_backtest(prices, target_weights, 1000.0, 1.0, 0.0, 0.0, 0.0)

    assert trades["side"].tolist() == ["BUY", "SELL"]
    assert trades["symbol"].tolist() == ["AAA", "AAA"]
    assert trades["date"].tolist() == [index[1], index[2]]
    assert (trades["notional"] > 0).all()
    assert (trades["estimated_cost"] > 0).all()
    assert trades["cash_flow"].iloc[0] < 0 < trades["cash_flow"].iloc[1]


def test_trailing_missing_price_is_liquidated_at_zero() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="D")
    prices = pd.DataFrame({"AAA": [10.0, 11.0, float("nan")]}, index=index)
    weights = pd.DataFrame({"AAA": [1.0, 1.0, 1.0]}, index=index)

    ledger, holdings, _ = run_backtest(
        prices, weights, 1000.0, 1.0, 0.0, 0.0, 0.0, True, 1
    )

    assert holdings.loc[index[-1], "AAA"] == 0.0
    assert ledger.loc[index[-1], "returns"] == -1.0
    assert (ledger["equity"] >= 0.0).all()


def test_execution_lag_is_configurable() -> None:
    index = pd.date_range("2020-01-01", periods=3, freq="D")
    prices = pd.DataFrame({"AAA": [10.0, 11.0, 12.0]}, index=index)
    weights = pd.DataFrame({"AAA": [1.0, 0.0, 0.0]}, index=index)

    one_day, _, _ = run_backtest(prices, weights, 1000.0, 0.0, 0.0, 0.0, 0.0)
    two_days, _, _ = run_backtest(
        prices, weights, 1000.0, 0.0, 0.0, 0.0, 0.0, execution_lag_days=2
    )

    assert one_day["equity"].iloc[-1] > two_days["equity"].iloc[-1]


def test_trade_pnl_remains_finite_when_entry_price_is_missing() -> None:
    index = pd.date_range("2020-01-01", periods=4, freq="D")
    prices = pd.DataFrame({"AAA": [10.0, 11.0, float("nan"), 12.0]}, index=index)
    weights = pd.DataFrame({"AAA": [0.0, 0.5, 0.0, 0.0]}, index=index)

    _, _, trades = run_backtest(prices, weights, 1000.0, 0.0, 0.0, 0.0, 0.0)

    assert trades["cumulative_net_profit_loss"].notna().all()
    assert trades["net_profit_loss"].notna().all()
    assert trades["side"].tolist() == ["BUY", "SELL"]
    assert trades["cumulative_net_profit_loss"].iloc[-1] > 0


def test_risk_diagnostics_and_period_filters_are_available() -> None:
    index = pd.date_range("2018-01-01", periods=160, freq="B")
    prices = pd.DataFrame(
        {
            "SPY": 100 * (1.0005 ** pd.Series(range(len(index)), index=index)),
            "AAA": 80 * (1.0008 ** pd.Series(range(len(index)), index=index)),
        },
        index=index,
    )

    diagnostics = risk_diagnostics(prices, "SPY", forecast_horizon_days=21, volatility_days=20)
    selected = select_period(prices, "2018-03-01", "2018-05-01")

    assert {"volatility", "reward_risk", "forecast_sharpe"} <= set(diagnostics)
    assert selected.index.min() >= pd.Timestamp("2018-03-01")
    assert selected.index.max() <= pd.Timestamp("2018-05-01")
    assert len(period_returns(pd.DataFrame({"equity": prices["SPY"]}), "M")) > 0


def test_buy_and_hold_and_lookahead_diagnostics() -> None:
    index = pd.date_range("2012-01-01", periods=500, freq="B")
    prices = pd.DataFrame(
        {
            "SPY": 100 * (1.001 ** pd.Series(range(len(index)), index=index)),
            "AAA": 50 * (1.002 ** pd.Series(range(len(index)), index=index)),
        },
        index=index,
    )
    weights = weekly_momentum_weights(
        prices, "SPY", top_n=1, lookback_days=20, skip_days=5, volatility_days=10
    )
    benchmark = buy_and_hold_backtest(prices, "SPY", 100_000, slippage_bps=5)

    assert benchmark["equity"].iloc[-1] > benchmark["equity"].iloc[0]
    assert len(
        segmented_performance(benchmark, {"sample": ("2012-01-01", "2013-12-31")})
    ) == 1
    assert not weights.empty
    assert_no_lookahead(
        prices,
        lambda frame, benchmark_name: weekly_momentum_weights(
            frame,
            benchmark_name,
            top_n=1,
            lookback_days=20,
            skip_days=5,
            volatility_days=10,
            volatility_target=0.20,
        ),
        "SPY",
        "2012-12-31",
    )
