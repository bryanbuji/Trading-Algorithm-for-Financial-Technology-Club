import pandas as pd

from trading.strategy import (
    _allocate_capped_inverse_volatility,
    weekly_momentum_weights,
)


def test_capped_allocation_redistributes_exposure() -> None:
    volatility = pd.Series([0.10, 0.20, 0.30, 0.40], index=list("ABCD"))
    allocation = _allocate_capped_inverse_volatility(volatility, 0.40, 0.10)

    assert allocation.sum() == 0.40
    assert (allocation <= 0.10).all()


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


def test_excluded_symbols_are_not_selected() -> None:
    index = pd.date_range("2012-01-01", periods=500, freq="B")
    prices = pd.DataFrame(
        {
            "SPY": 100 * (1.001 ** pd.Series(range(len(index)), index=index)),
            "AAA": 50 * (1.002 ** pd.Series(range(len(index)), index=index)),
            "BOND": 80 * (1.003 ** pd.Series(range(len(index)), index=index)),
        },
        index=index,
    )
    weights = weekly_momentum_weights(
        prices,
        "SPY",
        top_n=2,
        lookback_days=20,
        skip_days=5,
        volatility_days=10,
        max_position_weight=0.5,
        excluded_symbols=["BOND"],
    )
    assert (weights["BOND"] == 0).all()


def test_recent_missing_observation_does_not_zero_all_signals() -> None:
    index = pd.date_range("2012-01-01", periods=500, freq="B")
    prices = pd.DataFrame(
        {
            "SPY": 100 * (1.001 ** pd.Series(range(len(index)), index=index)),
            "AAA": 50 * (1.002 ** pd.Series(range(len(index)), index=index)),
        },
        index=index,
    )
    prices.iloc[-1, 1] = float("nan")
    weights = weekly_momentum_weights(
        prices,
        "SPY",
        top_n=1,
        lookback_days=20,
        skip_days=5,
        volatility_days=10,
        max_position_weight=0.5,
        stop_loss_pct=1.0,
    )
    assert weights.iloc[-1]["AAA"] > 0
