from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def build_feature_panel(prices: pd.DataFrame, benchmark: str) -> Tuple[pd.DataFrame, pd.Series]:
    prices = prices.resample("W-FRI").last().replace([np.inf, -np.inf], np.nan)
    prices = prices.where(prices > 0).ffill()
    returns = prices.pct_change(fill_method=None)
    benchmark_return = returns[benchmark]
    frames = []
    targets = []
    for symbol in prices.columns:
        if symbol == benchmark:
            continue
        series = prices[symbol]
        features = pd.DataFrame(
            {
                "momentum_21d": series.shift(1).div(series.shift(22)).sub(1),
                "momentum_63d": series.shift(1).div(series.shift(64)).sub(1),
                "momentum_126d": series.shift(1).div(series.shift(127)).sub(1),
                "volatility_63d": returns[symbol].shift(1).rolling(63).std() * np.sqrt(252),
                "relative_strength_63d": returns[symbol].shift(1).rolling(63).sum()
                - benchmark_return.shift(1).rolling(63).sum(),
                "benchmark_volatility_63d": benchmark_return.shift(1).rolling(63).std()
                * np.sqrt(252),
            }
        )
        features["symbol"] = symbol
        frames.append(features)
        targets.append(series.shift(-21).div(series).sub(1).rename("target"))
    panel = pd.concat(frames).reset_index().rename(columns={"Date": "date", "index": "date"})
    target = pd.concat(targets).reset_index(drop=True)
    panel["target"] = target
    panel = panel.replace([np.inf, -np.inf], np.nan).dropna()
    feature_names = [column for column in panel.columns if column not in {"date", "symbol", "target"}]
    panel[feature_names] = panel[feature_names].clip(-10.0, 10.0)
    panel["target"] = panel["target"].clip(-1.0, 1.0)
    panel = panel.set_index(["date", "symbol"]).sort_index()
    target = panel.pop("target")
    return panel, target


def walk_forward_predictions(
    prices: pd.DataFrame,
    benchmark: str,
    min_train_days: int = 260,
    retrain_days: int = 13,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    panel, target = build_feature_panel(prices, benchmark)
    feature_names = list(panel.columns)
    dates = sorted(panel.index.get_level_values("date").unique())
    predictions = []
    # Features are already clipped to bounded ranges. The iterative solver
    # avoids the dense standardized matmul overflow seen on long histories.
    model = Ridge(alpha=1.0, solver="lsqr")
    for index, date in enumerate(dates):
        if index < min_train_days or index % retrain_days != 0:
            continue
        train_dates = dates[:index]
        train_mask = panel.index.get_level_values("date").isin(train_dates)
        test_mask = panel.index.get_level_values("date") == date
        if not test_mask.any():
            continue
        train_features = panel.loc[train_mask, feature_names]
        train_target = target.loc[train_mask]
        valid_train = np.isfinite(train_features).all(axis=1) & np.isfinite(train_target)
        valid_test = np.isfinite(panel.loc[test_mask, feature_names]).all(axis=1)
        if valid_train.sum() < len(feature_names) or not valid_test.any():
            continue
        model.fit(train_features.loc[valid_train], train_target.loc[valid_train])
        prediction = np.clip(
            model.predict(panel.loc[test_mask, feature_names].loc[valid_test]), -1.0, 1.0
        )
        test_keys = panel.index[test_mask][valid_test]
        for key, value in zip(test_keys, prediction):
            predictions.append({"date": key[0], "symbol": key[1], "prediction": value})
    prediction_frame = pd.DataFrame(predictions)
    if prediction_frame.empty:
        return pd.DataFrame(), {"observations": 0.0, "correlation": float("nan")}
    prediction_frame = prediction_frame.pivot(index="date", columns="symbol", values="prediction")
    aligned_target = target.reset_index().pivot(index="date", columns="symbol", values="target")
    common = prediction_frame.stack().rename("prediction").to_frame().join(
        aligned_target.stack().rename("target"), how="inner"
    )
    correlation = common["prediction"].corr(common["target"])
    return prediction_frame, {
        "observations": float(len(common)),
        "correlation": float(correlation),
        "features": float(len(feature_names)),
    }
