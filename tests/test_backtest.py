import pandas as pd

from trading.backtest import format_performance_report, run_backtest


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

    assert trades["side"].tolist() == ["BUY", "SELL", "BUY"]
    assert trades["symbol"].tolist() == ["AAA", "AAA", "AAA"]
    assert trades["notional"].round(3).tolist() == [500.0, 500.0, 262.488]
    assert trades["net_profit_loss"].round(3).tolist() == [0.0, 45.405, 0.0]
    assert trades["profit_loss_pct"].round(3).tolist() == [0.0, 0.091, 0.0]
