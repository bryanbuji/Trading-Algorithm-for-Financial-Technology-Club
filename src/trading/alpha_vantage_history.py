"""Resumable Alpha Vantage daily adjusted-price downloads."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import deque
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
DEFAULT_DAILY_LIMIT = 25
RATE_WINDOW_SECONDS = 60.0
DAILY_WINDOW_SECONDS = 24.0 * 60.0 * 60.0


class ApiResponseError(RuntimeError):
    """Alpha Vantage returned a valid response without usable prices."""


class ApiRateLimitError(RuntimeError):
    """Alpha Vantage returned a rate-limit or quota message."""


class ApiKeyError(RuntimeError):
    """Alpha Vantage rejected the configured API key."""


class ApiAccessError(RuntimeError):
    """The API key does not have access to the requested endpoint."""


class DailyQuotaExceeded(RuntimeError):
    """The locally tracked daily request allowance is exhausted."""


def _provider_error(message: str) -> RuntimeError:
    lower = message.lower()
    if "api key" in lower or "apikey" in lower or "invalid key" in lower:
        return ApiKeyError(message)
    if (
        "rate limit" in lower
        or "call frequency" in lower
        or "too many requests" in lower
        or "per minute" in lower
    ):
        return ApiRateLimitError(message)
    if "per day" in lower or "daily limit" in lower or "requests per day" in lower:
        return DailyQuotaExceeded(message)
    if "premium" in lower or "entitlement" in lower or "subscription" in lower:
        return ApiAccessError(message)
    return ApiResponseError(message)


class RequestLedger:
    """Persist request timestamps and enforce rolling-minute/day limits."""

    def __init__(
        self,
        path: Path,
        max_calls_per_minute: int = 5,
        max_calls_per_day: int | None = DEFAULT_DAILY_LIMIT,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not 1 <= max_calls_per_minute <= 5:
            raise ValueError("max_calls_per_minute must be between 1 and 5")
        if max_calls_per_day is not None and max_calls_per_day < 1:
            raise ValueError("max_calls_per_day must be positive or None")
        self.path = path
        self.max_calls_per_minute = max_calls_per_minute
        self.max_calls_per_day = max_calls_per_day
        self.sleep = sleep
        self.clock = clock
        self.calls = deque(self._read_calls())

    def _read_calls(self) -> list[float]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return [float(value) for value in payload if float(value) > self.clock() - DAILY_WINDOW_SECONDS]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return []

    def _save_calls(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=self.path.parent, delete=False, encoding="utf-8"
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(list(self.calls), temporary)
        os.replace(temporary_path, self.path)

    def acquire(self) -> None:
        while True:
            now = self.clock()
            while self.calls and self.calls[0] <= now - DAILY_WINDOW_SECONDS:
                self.calls.popleft()
            minute_calls = [stamp for stamp in self.calls if stamp > now - RATE_WINDOW_SECONDS]
            if self.max_calls_per_day is not None and len(self.calls) >= self.max_calls_per_day:
                raise DailyQuotaExceeded(
                    f"Local Alpha Vantage budget of {self.max_calls_per_day} calls per rolling 24 hours is exhausted"
                )
            if len(minute_calls) < self.max_calls_per_minute:
                self.calls.append(now)
                self._save_calls()
                return
            delay = max(0.0, minute_calls[0] + RATE_WINDOW_SECONDS - now) + 0.05
            self.sleep(delay)


def load_ticker_requests(path: Path) -> list[dict[str, str]]:
    """Read a newline list or CSV with symbol, optional api_symbol and status."""
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=str).fillna("")
        columns = {str(column).strip().lower(): column for column in frame.columns}
        symbol_column = columns.get("symbol") or columns.get("ticker")
        if symbol_column is None:
            raise ValueError("Ticker CSV requires a 'symbol' or 'ticker' column")
        requests_out = []
        for row in frame.to_dict(orient="records"):
            symbol = str(row[symbol_column]).strip()
            if symbol:
                requests_out.append(
                    {
                        "symbol": symbol,
                        "api_symbol": str(row.get(columns.get("api_symbol", ""), "")).strip() or symbol,
                        "status": str(row.get(columns.get("status", ""), "active")).strip().lower() or "active",
                    }
                )
        return requests_out

    return [
        {"symbol": symbol, "api_symbol": symbol, "status": "active"}
        for line in path.read_text(encoding="utf-8").splitlines()
        if (symbol := line.strip()) and not symbol.startswith("#")
    ]


def _safe_filename(symbol: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", symbol.strip())
    if not name or name in {".", ".."}:
        raise ValueError(f"Invalid ticker symbol {symbol!r}")
    return name


def _cache_is_valid(path: Path, symbol: str, api_symbol: str) -> bool:
    if not path.exists():
        return False
    try:
        frame = pd.read_csv(path)
        return (
            not frame.empty
            and {"date", "adjusted_close", "symbol", "api_symbol"}.issubset(frame.columns)
            and frame["symbol"].eq(symbol).all()
            and frame["api_symbol"].eq(api_symbol).all()
            and pd.to_numeric(frame["adjusted_close"], errors="coerce").notna().all()
        )
    except (OSError, pd.errors.ParserError, ValueError):
        return False


def parse_adjusted_daily_payload(
    payload: Any,
    symbol: str,
    api_symbol: str,
    status: str,
) -> pd.DataFrame:
    """Validate and normalize one Alpha Vantage adjusted daily JSON payload."""
    if not isinstance(payload, dict):
        raise ApiResponseError("Response JSON must be an object")
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        message = (
            payload.get("Error Message")
            or payload.get("Note")
            or payload.get("Information")
            or "empty response or missing 'Time Series (Daily)' field"
        )
        raise _provider_error(str(message))

    frame = pd.DataFrame.from_dict(series, orient="index")
    field_map = {
        "1. open": "open",
        "2. high": "high",
        "3. low": "low",
        "4. close": "close",
        "5. adjusted close": "adjusted_close",
        "6. volume": "volume",
        "7. dividend amount": "dividend_amount",
        "8. split coefficient": "split_coefficient",
    }
    frame = frame.rename(columns=field_map)
    if "adjusted_close" not in frame:
        raise ApiResponseError("Adjusted daily response has no '5. adjusted close' field")
    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame.index.name = "date"
    frame = frame.reset_index()
    frame = frame.dropna(subset=["date"])
    for column in field_map.values():
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["adjusted_close"]).sort_values("date")
    if frame.empty:
        raise ApiResponseError("Adjusted daily series contained no valid observations")
    frame.insert(1, "symbol", symbol)
    frame.insert(2, "api_symbol", api_symbol)
    frame.insert(3, "listing_status", status)
    return frame


class AlphaVantageHistoryDownloader:
    def __init__(
        self,
        api_key: str,
        data_dir: Path,
        session: requests.Session | None = None,
        limiter: RequestLedger | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
        timeout: float = 30.0,
        listing_status_date: str | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_retries = max_retries
        self.timeout = timeout
        self.listing_status_date = listing_status_date
        self.limiter = limiter or RequestLedger(self.data_dir / ".request_history.json", sleep=sleep)
        self.error_log = self.data_dir / "error_log.txt"

    def _log_error(self, symbol: str, api_symbol: str, error: BaseException) -> None:
        message = str(error).replace(self.api_key, "[REDACTED]") if self.api_key else str(error)
        message = re.sub(r"(?i)(apikey=)[^&\s]+", r"\1[REDACTED]", message)
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        with self.error_log.open("a", encoding="utf-8") as stream:
            stream.write(
                f"{timestamp} | ticker={symbol or '-'} | api_symbol={api_symbol or '-'} "
                f"| {type(error).__name__}: {message}\n"
            )

    def _request_payload(self, api_symbol: str) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            try:
                response = self.session.get(
                    ALPHA_VANTAGE_URL,
                    params={
                        "function": "TIME_SERIES_DAILY_ADJUSTED",
                        "symbol": api_symbol,
                        "outputsize": "full",
                        "apikey": self.api_key,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.exceptions.JSONDecodeError as error:
                raise ApiResponseError("Invalid JSON response") from error
            except requests.exceptions.RequestException as error:
                status_code = getattr(getattr(error, "response", None), "status_code", None)
                if status_code in {401, 403}:
                    raise ApiAccessError(f"Alpha Vantage rejected the request with HTTP {status_code}") from error
                if status_code == 429:
                    if attempt >= self.max_retries:
                        raise ApiRateLimitError("Alpha Vantage returned HTTP 429 after retries") from error
                    self.sleep(min(900.0, 60.0 * (2**attempt)))
                    continue
                if attempt >= self.max_retries:
                    raise
                self.sleep(min(60.0, 2.0**attempt * 5.0))
                continue

            if not isinstance(payload, dict):
                raise ApiResponseError("Response JSON must be an object")
            message = (
                payload.get("Error Message")
                or payload.get("Note")
                or payload.get("Information")
            )
            if message:
                error = _provider_error(str(message))
                if isinstance(error, ApiRateLimitError):
                    if attempt >= self.max_retries:
                        raise error
                    self.sleep(min(900.0, 60.0 * (2**attempt)))
                    continue
                raise error
            return payload
        raise ApiRateLimitError("Retry limit reached")

    def fetch_listing_status(self, state: str = "delisted") -> pd.DataFrame:
        """Fetch the separate Alpha Vantage listing/delisting CSV endpoint."""
        if state not in {"active", "delisted"}:
            raise ValueError("state must be 'active' or 'delisted'")
        date_part = self.listing_status_date or "latest"
        path = self.data_dir / f"listing_status_{state}_{date_part}.csv"
        if path.exists():
            try:
                cached = pd.read_csv(path)
                if "symbol" in {str(col).lower() for col in cached.columns}:
                    return cached
            except (OSError, pd.errors.ParserError):
                pass

        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            try:
                response = self.session.get(
                    ALPHA_VANTAGE_URL,
                    params={
                        "function": "LISTING_STATUS",
                        "state": state,
                        "date": self.listing_status_date,
                        "apikey": self.api_key,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as error:
                status_code = getattr(getattr(error, "response", None), "status_code", None)
                if status_code in {401, 403}:
                    raise ApiAccessError(f"Listing-status request rejected with HTTP {status_code}") from error
                if status_code == 429:
                    if attempt >= self.max_retries:
                        raise ApiRateLimitError("Listing-status request returned HTTP 429") from error
                    self.sleep(min(900.0, 60.0 * (2**attempt)))
                    continue
                if attempt >= self.max_retries:
                    raise
                self.sleep(min(60.0, 5.0 * (2**attempt)))
                continue

            try:
                frame = pd.read_csv(StringIO(response.text))
            except (pd.errors.ParserError, ValueError):
                frame = pd.DataFrame()
            if frame.empty or "symbol" not in {str(col).lower() for col in frame.columns}:
                try:
                    payload = response.json()
                except requests.exceptions.JSONDecodeError:
                    payload = {}
                message = (
                    payload.get("Error Message")
                    or payload.get("Note")
                    or payload.get("Information")
                    or "Listing-status response has no symbol records"
                ) if isinstance(payload, dict) else "invalid listing-status response"
                error = _provider_error(str(message))
                if isinstance(error, ApiRateLimitError):
                    if attempt >= self.max_retries:
                        raise error
                    self.sleep(min(900.0, 60.0 * (2**attempt)))
                    continue
                raise error
            frame.to_csv(path, index=False)
            return frame
        raise ApiRateLimitError("Listing-status retry limit reached")

    def download(self, tickers: Iterable[dict[str, str]]) -> dict[str, int]:
        if not self.api_key:
            error = ApiKeyError("ALPHAVANTAGE_API_KEY is not set")
            self._log_error("", "", error)
            return {"saved": 0, "cached": 0, "failed": 1, "deferred": len(list(tickers))}

        stats = {"saved": 0, "cached": 0, "failed": 0, "deferred": 0}
        ticker_list = list(tickers)
        uncached_delisted = [
            item
            for item in ticker_list
            if item.get("status", "active").lower() == "delisted"
            and not _cache_is_valid(
                self.data_dir / f"{_safe_filename(item['symbol'])}.csv",
                item["symbol"],
                item.get("api_symbol", item["symbol"]),
            )
        ]
        if uncached_delisted:
            try:
                listing = self.fetch_listing_status("delisted")
                symbol_column = next(col for col in listing.columns if str(col).lower() == "symbol")
                listed_symbols = set(listing[symbol_column].astype(str).str.upper())
                for item in uncached_delisted:
                    if item.get("api_symbol", item["symbol"]).upper() not in listed_symbols:
                        self._log_error(
                            item["symbol"],
                            item.get("api_symbol", item["symbol"]),
                            ApiResponseError(
                                "Ticker was not present in the Alpha Vantage delisted listing snapshot; price lookup will still be attempted"
                            ),
                        )
            except DailyQuotaExceeded as error:
                self._log_error("", "", error)
                stats["deferred"] = len(ticker_list)
                return stats
            except (ApiKeyError, ApiRateLimitError) as error:
                self._log_error("", "", error)
                stats["failed"] = 1
                stats["deferred"] = len(ticker_list)
                return stats
            except (
                ApiAccessError,
                ApiResponseError,
                OSError,
                ValueError,
                requests.exceptions.RequestException,
                pd.errors.ParserError,
            ) as error:
                self._log_error("", "", error)

        for position, item in enumerate(ticker_list):
            symbol = item["symbol"].strip()
            api_symbol = item.get("api_symbol", symbol).strip()
            status = item.get("status", "active").strip().lower() or "active"
            try:
                cache_path = self.data_dir / f"{_safe_filename(symbol)}.csv"
            except ValueError as error:
                self._log_error(symbol, api_symbol, error)
                stats["failed"] += 1
                continue
            if _cache_is_valid(cache_path, symbol, api_symbol):
                stats["cached"] += 1
                print(f"[{position + 1}/{len(ticker_list)}] cached {symbol}")
                continue
            try:
                payload = self._request_payload(api_symbol)
                frame = parse_adjusted_daily_payload(payload, symbol, api_symbol, status)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".csv", dir=cache_path.parent, delete=False, encoding="utf-8"
                ) as temporary:
                    temporary_path = Path(temporary.name)
                    frame.to_csv(temporary, index=False)
                os.replace(temporary_path, cache_path)
                stats["saved"] += 1
                print(f"[{position + 1}/{len(ticker_list)}] saved {symbol} ({len(frame):,} rows)")
            except DailyQuotaExceeded as error:
                self._log_error(symbol, api_symbol, error)
                stats["deferred"] = len(ticker_list) - position
                break
            except ApiKeyError as error:
                self._log_error(symbol, api_symbol, error)
                stats["failed"] += 1
                stats["deferred"] = len(ticker_list) - position - 1
                break
            except ApiAccessError as error:
                self._log_error(symbol, api_symbol, error)
                stats["failed"] += 1
                stats["deferred"] = len(ticker_list) - position - 1
                break
            except Exception as error:  # noqa: BLE001  # Log a bad ticker and continue the batch.
                self._log_error(symbol, api_symbol, error)
                stats["failed"] += 1
                print(f"[{position + 1}/{len(ticker_list)}] failed {symbol}; see {self.error_log}")
        cached_files = [
            self.data_dir / f"{_safe_filename(item['symbol'])}.csv"
            for item in ticker_list
            if _cache_is_valid(
                self.data_dir / f"{_safe_filename(item['symbol'])}.csv",
                item["symbol"],
                item.get("api_symbol", item["symbol"]),
            )
        ]
        if cached_files:
            combined = pd.concat((pd.read_csv(path) for path in cached_files), ignore_index=True)
            output_path = self.data_dir / "alpha_vantage_adjusted_history.csv"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", dir=self.data_dir, delete=False, encoding="utf-8"
            ) as temporary:
                temporary_path = Path(temporary.name)
                combined.to_csv(temporary, index=False)
            os.replace(temporary_path, output_path)
        return stats

