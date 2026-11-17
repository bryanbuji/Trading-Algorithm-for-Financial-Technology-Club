import pandas as pd

from trading import data


def test_configured_symbols_add_current_sp500_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(data, "sp500_symbols", lambda: ["AAA", "BRK-B"])
    config = {
        "symbols": ["SPY"],
        "include_current_sp500": True,
        "asset_classes": {"equities": ["DIA"]},
        "benchmark": "SPY",
        "nasdaq_benchmark": "QQQ",
    }

    symbols = data.configured_symbols(config)

    assert symbols == ["SPY", "AAA", "BRK-B", "DIA", "QQQ"]


def test_sp500_symbols_parses_wikipedia_table(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"html"

    captured = []
    names = [f"TICKER{i}" for i in range(251)]
    names[1] = "BRK.B"

    def fake_read_html(source):
        captured.append(source)
        return [pd.DataFrame({"Symbol": names})]

    monkeypatch.setattr(data, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(data.pd, "read_html", fake_read_html)

    symbols = data.sp500_symbols()

    assert symbols[:2] == ["TICKER0", "BRK-B"]
    assert len(symbols) == 251
    assert captured[0].read() == b"html"


def test_sp500_membership_mask_reconstructs_snapshots_without_projecting_members():
    snapshots = pd.DataFrame(
        {"tickers": [["AAA", "BBB"], ["BBB", "CCC"]]},
        index=pd.to_datetime(["2020-01-01", "2020-01-03"]),
    )
    dates = pd.date_range("2020-01-01", periods=4, freq="D")
    symbols = pd.Index(["AAA", "BBB", "CCC", "DDD", "QQQ"])

    membership = data.sp500_membership_mask(
        dates, symbols, snapshots, current_symbols=["CCC", "DDD"]
    )

    assert membership["AAA"].tolist() == [True, True, False, False]
    assert membership["BBB"].tolist() == [True, True, True, True]
    assert membership["CCC"].tolist() == [False, False, True, True]
    assert not membership["DDD"].any()
    assert membership["QQQ"].all()


def test_current_roster_only_reconciles_at_current_snapshot_date():
    snapshots = pd.DataFrame(
        {"tickers": [["AAA"]]}, index=pd.to_datetime(["2020-01-01"])
    )
    as_of = pd.Timestamp("2026-10-29")
    dates = pd.DatetimeIndex([as_of - pd.Timedelta(days=1), as_of])

    membership = data.sp500_membership_mask(
        dates,
        pd.Index(["AAA", "BBB"]),
        snapshots,
        current_symbols=["BBB"],
        current_as_of=as_of,
    )

    assert membership["BBB"].tolist() == [False, True]


def test_yahoo_download_batches_tickers_and_combines_close_prices(monkeypatch, tmp_path) -> None:
    requested = []
    index = pd.date_range("2020-01-01", periods=2)

    def fake_download(symbols, **kwargs):
        requested.append(symbols)
        columns = pd.MultiIndex.from_product([["Close"], symbols])
        return pd.DataFrame([[10.0] * len(symbols), [11.0] * len(symbols)], index=index, columns=columns)

    monkeypatch.setattr(data.yf, "download", fake_download)
    result = data.download_prices(
        ["A", "B", "C"],
        "2020-01-01",
        cache_path=tmp_path / "prices.parquet",
        batch_size=2,
        pause_seconds=0,
    )

    assert requested == [["A", "B"], ["C"]]
    assert result.columns.tolist() == ["A", "B", "C"]
    assert result.iloc[-1].tolist() == [11.0, 11.0, 11.0]
