import pandas as pd

from trading.visualization import monthly_cash_flow, plot_monthly_cash_flow


def test_monthly_cash_flow_has_auditable_monthly_totals() -> None:
    trades = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-03", "2020-01-10", "2020-02-04"]),
            "symbol": ["AAA", "AAA", "BBB"],
            "cash_flow": [-500.0, 550.0, -200.0],
            "net_profit_loss": [0.0, 50.0, 0.0],
            "estimated_cost": [1.0, 1.0, 0.5],
        }
    )

    result = monthly_cash_flow(trades)

    assert result.loc["2020-01-31", "cash_flow"] == 50.0
    assert result.loc["2020-02-29", "cash_flow"] == -200.0
    assert result.loc["2020-01-31", "trade_count"] == 2


def test_monthly_cash_flow_plot_always_has_twelve_bars() -> None:
    trades = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-03"]),
            "symbol": ["AAA"],
            "cash_flow": [-500.0],
        }
    )

    _, axis = plot_monthly_cash_flow(trades, 2020)

    assert len(axis.patches) == 12
