import json

import pandas as pd
import pytest

from trading import open_data


def test_alpha_vantage_parses_adjusted_close(monkeypatch) -> None:
    payload = {
        "Time Series (Daily)": {
            "2020-01-02": {"5. adjusted close": "10.5"},
            "2020-01-01": {"5. adjusted close": "10.0"},
        }
    }

    def fake_request(*args, **kwargs):
        return payload

    monkeypatch.setattr(open_data, "_json_request", fake_request)
    result = open_data.alpha_vantage_daily_adjusted("ABC", api_key="test")
    assert result.index.is_monotonic_increasing
    assert result.iloc[-1] == 10.5


def test_alpha_vantage_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ALPHAVANTAGE_API_KEY"):
        open_data.alpha_vantage_daily_adjusted("ABC")


def test_alpha_prices_expand_yahoo_cache_without_replacing_values(monkeypatch) -> None:
    yahoo = pd.DataFrame(
        {"ABC": [1.0, None]},
        index=pd.date_range("2020-01-01", periods=2),
    )
    alpha = pd.Series(
        [2.0, 3.0],
        index=pd.date_range("2020-01-02", periods=2),
        name="ABC",
    )
    monkeypatch.setattr(
        open_data,
        "alpha_vantage_daily_adjusted",
        lambda symbol, api_key=None: alpha,
    )
    result = open_data.merge_alpha_vantage_prices(yahoo, ["ABC"])
    assert result.loc["2020-01-01", "ABC"] == 1.0
    assert result.loc["2020-01-02", "ABC"] == 2.0
    assert result.loc["2020-01-03", "ABC"] == 3.0


def test_fred_parses_public_csv(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"observation_date,SP500\n2020-01-01,3200\n"

    monkeypatch.setattr(open_data, "urlopen", lambda *args, **kwargs: Response())
    result = open_data.fred_series("SP500")
    assert result.iloc[0] == 3200


def test_sec_requires_identifying_user_agent(monkeypatch) -> None:
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        open_data.sec_submissions("320193")
