import numpy as np
import pandas as pd

from ml_trade_model.modeling import build_feature_panel, walk_forward_predictions


def test_features_and_predictions_are_finite() -> None:
    index = pd.date_range("2018-01-01", periods=420, freq="B")
    prices = pd.DataFrame(
        {
            "SPY": 100 * (1.0002 ** pd.Series(range(len(index)), index=index)),
            "AAA": 80 * (1.0004 ** pd.Series(range(len(index)), index=index)),
        },
        index=index,
    )
    panel, target = build_feature_panel(prices, "SPY")
    predictions, _ = walk_forward_predictions(
        prices, "SPY", min_train_days=20, retrain_days=4
    )

    assert np.isfinite(panel.to_numpy()).all()
    assert np.isfinite(target.to_numpy()).all()
    assert np.isfinite(predictions.to_numpy()).all()
