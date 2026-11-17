
import pandas as pd
import requests

from trading.alpha_vantage_history import (
    AlphaVantageHistoryDownloader,
    ApiResponseError,
    RequestLedger,
    load_ticker_requests,
    parse_adjusted_daily_payload,
)


def payload(adjusted_close="10.5"):
    return {
        "Meta Data": {"2. Symbol": "ABC"},
        "Time Series (Daily)": {
            "2020-01-02": {
                "1. open": "11.0",
                "2. high": "12.0",
                "3. low": "9.0",
                "4. close": "10.0",
                "5. adjusted close": adjusted_close,
                "6. volume": "1000",
                "7. dividend amount": "0.0",
                "8. split coefficient": "1.0",
            }
        },
    }


class FakeResponse:
    status_code = 200

    def __init__(self, body, text=""):
        self.body = body
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return self.responses.pop(0)


def test_parse_adjusted_payload_normalizes_prices() -> None:
    frame = parse_adjusted_daily_payload(payload(), "ABC", "ABC", "active")

    assert frame.loc[0, "adjusted_close"] == 10.5
    assert frame.loc[0, "symbol"] == "ABC"
    assert frame.loc[0, "listing_status"] == "active"


def test_empty_or_invalid_payload_is_safe_error() -> None:
    for response in ({}, {"Time Series (Daily)": {}}):
        try:
            parse_adjusted_daily_payload(response, "ABC", "ABC", "delisted")
        except ApiResponseError:
            pass
        else:
            raise AssertionError("expected malformed response to be rejected")


def test_ticker_csv_accepts_explicit_api_alias_and_delisted_status(tmp_path) -> None:
    source = tmp_path / "tickers.csv"
    pd.DataFrame(
        [{"symbol": "OLD", "api_symbol": "NEW", "status": "delisted"}]
    ).to_csv(source, index=False)

    result = load_ticker_requests(source)

    assert result == [{"symbol": "OLD", "api_symbol": "NEW", "status": "delisted"}]


def test_downloader_saves_immediately_and_skips_valid_cache(tmp_path) -> None:
    session = FakeSession([FakeResponse(payload())])
    limiter = RequestLedger(
        tmp_path / ".request_history.json", max_calls_per_day=10, sleep=lambda _: None
    )
    downloader = AlphaVantageHistoryDownloader(
        "secret", tmp_path, session=session, limiter=limiter, sleep=lambda _: None
    )
    ticker = {"symbol": "ABC", "api_symbol": "ABC", "status": "active"}

    first = downloader.download([ticker])
    cache = pd.read_csv(tmp_path / "ABC.csv")
    second = downloader.download([ticker])

    assert first["saved"] == 1
    assert second["cached"] == 1
    assert len(session.calls) == 1
    assert session.calls[0][1]["function"] == "TIME_SERIES_DAILY_ADJUSTED"
    assert "state" not in session.calls[0][1]
    assert cache.loc[0, "adjusted_close"] == 10.5


def test_rate_limiter_observes_strict_rolling_minute_limit(tmp_path) -> None:
    now = [1000.0]
    delays = []

    def sleep(seconds):
        delays.append(seconds)
        now[0] += seconds

    ledger = RequestLedger(
        tmp_path / "history.json",
        max_calls_per_minute=5,
        max_calls_per_day=10,
        sleep=sleep,
        clock=lambda: now[0],
    )
    for _ in range(5):
        ledger.acquire()
    ledger.acquire()

    assert len(delays) == 1
    assert delays[0] >= 60


def test_rate_limit_warning_backs_off_and_retries(tmp_path) -> None:
    session = FakeSession(
        [
            FakeResponse({"Note": "Thank you. Standard API call frequency limit reached."}),
            FakeResponse(payload()),
        ]
    )
    sleeps = []
    limiter = RequestLedger(
        tmp_path / "history.json", max_calls_per_day=10, sleep=lambda _: None
    )
    downloader = AlphaVantageHistoryDownloader(
        "secret", tmp_path, session=session, limiter=limiter, sleep=sleeps.append
    )

    stats = downloader.download([{"symbol": "ABC", "api_symbol": "ABC", "status": "active"}])

    assert stats["saved"] == 1
    assert len(session.calls) == 2
    assert sleeps == [60.0]


def test_delisted_ticker_uses_separate_listing_status_parameters(tmp_path) -> None:
    session = FakeSession(
        [
            FakeResponse(None, text="symbol,name\nOLD,Old Corp\n"),
            FakeResponse(payload()),
        ]
    )
    limiter = RequestLedger(
        tmp_path / "history.json", max_calls_per_day=10, sleep=lambda _: None
    )
    downloader = AlphaVantageHistoryDownloader(
        "secret",
        tmp_path,
        session=session,
        limiter=limiter,
        sleep=lambda _: None,
        listing_status_date="2020-01-02",
    )

    stats = downloader.download(
        [{"symbol": "OLD", "api_symbol": "OLD", "status": "delisted"}]
    )

    assert stats["saved"] == 1
    listing_params = session.calls[0][1]
    price_params = session.calls[1][1]
    assert listing_params["function"] == "LISTING_STATUS"
    assert listing_params["state"] == "delisted"
    assert listing_params["date"] == "2020-01-02"
    assert price_params["function"] == "TIME_SERIES_DAILY_ADJUSTED"
    assert "state" not in price_params


def test_invalid_json_is_logged_and_next_ticker_continues(tmp_path) -> None:
    session = FakeSession(
        [
            FakeResponse(requests.exceptions.JSONDecodeError("bad json", "<html>", 0)),
            FakeResponse(payload()),
        ]
    )
    limiter = RequestLedger(
        tmp_path / "history.json", max_calls_per_day=10, sleep=lambda _: None
    )
    downloader = AlphaVantageHistoryDownloader(
        "secret", tmp_path, session=session, limiter=limiter, sleep=lambda _: None
    )

    stats = downloader.download(
        [
            {"symbol": "BAD", "api_symbol": "BAD", "status": "active"},
            {"symbol": "ABC", "api_symbol": "ABC", "status": "active"},
        ]
    )

    assert stats["failed"] == 1
    assert stats["saved"] == 1
    assert "Invalid JSON response" in (tmp_path / "error_log.txt").read_text()
    assert "secret" not in (tmp_path / "error_log.txt").read_text()
