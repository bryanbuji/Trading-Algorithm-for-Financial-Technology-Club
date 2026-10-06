import pandas as pd

from trading.strategy import weekly_momentum_weights


def test_weights_are_capped_and_nonnegative() -> None:
    index = pd.date_range("2012-01-01", periods=500, freq="B")
    prices = pd.DataFrame(
        {
            "SPY": 100 * (1.001 ** pd.Series(range(len(index)), index=index)),
            "AAA": 50 * (1.002 ** pd.Series(range(len(index)), index=index)),
            "BBB": 80 * (1.0015 ** pd.Series(range(len(index)), index=index)),
        },
        index=index,
    )
    weights = weekly_momentum_weights(prices, "SPY", top_n=2, max_position_weight=0.10)
    assert (weights >= 0).all().all()
    assert (weights.sum(axis=1) <= 1.0 + 1e-9).all()
    assert (weights.max(axis=1) <= 0.10 + 1e-9).all()
