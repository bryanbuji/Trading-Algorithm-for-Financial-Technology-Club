import pandas as pd

from trading.backtest import format_performance_report


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
