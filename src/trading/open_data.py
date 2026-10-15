"""Optional adapters for free Alpha Vantage, FRED, and SEC EDGAR data."""

import io
import json
import os
from datetime import date
from typing import Any, Optional, Union
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

DateLike = Union[str, date]
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def _json_request(url: str, params: dict[str, Any], headers: dict[str, str]) -> Any:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    request = Request(f"{url}?{query}", headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except HTTPError as error:
        raise RuntimeError(f"Data provider request failed with HTTP {error.code}.") from error


def alpha_vantage_daily_adjusted(
    symbol: str,
    api_key: Optional[str] = None,
    outputsize: str = "full",
) -> pd.Series:
    """Return Alpha Vantage adjusted close data for one symbol.

    Alpha Vantage requires a free API key and has strict free-tier limits.
    """
    key = (api_key or os.getenv("ALPHAVANTAGE_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("Set ALPHAVANTAGE_API_KEY before using Alpha Vantage.")
    if outputsize not in {"compact", "full"}:
        raise ValueError("outputsize must be compact or full")
    payload = _json_request(
        ALPHA_VANTAGE_URL,
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": key,
        },
        {"User-Agent": "trading-research/1.0"},
    )
    if "Error Message" in payload or "Note" in payload:
        message = payload.get("Error Message") or payload["Note"]
        raise RuntimeError(f"Alpha Vantage rejected {symbol}: {message}")
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict):
        raise RuntimeError(f"Alpha Vantage returned no daily series for {symbol}.")
    frame = pd.DataFrame.from_dict(series, orient="index")
    adjusted_column = "5. adjusted close"
    if adjusted_column not in frame:
        raise RuntimeError(f"Alpha Vantage response has no adjusted close for {symbol}.")
    result = frame[adjusted_column].astype(float)
    result.index = pd.to_datetime(result.index)
    return result.sort_index().rename(symbol)


def merge_alpha_vantage_prices(
    yahoo_prices: pd.DataFrame,
    symbols: list[str],
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """Add Alpha Vantage histories to the Yahoo cache without replacing Yahoo data."""
    result = yahoo_prices.copy()
    for symbol in dict.fromkeys(symbols):
        alpha_prices = alpha_vantage_daily_adjusted(symbol, api_key=api_key)
        alpha_frame = alpha_prices.to_frame()
        if symbol in result:
            result = result.combine_first(alpha_frame)
        else:
            result = result.join(alpha_frame, how="outer")
    result.index = pd.to_datetime(result.index).tz_localize(None)
    return result.sort_index()


def fred_series(
    series_id: str,
    start: Optional[DateLike] = None,
    end: Optional[DateLike] = None,
) -> pd.Series:
    """Download a public FRED CSV series; no FRED API key is required."""
    query = urlencode(
        {
            "id": series_id,
            "cosd": start,
            "coed": end,
        }
    )
    request = Request(
        f"{FRED_CSV_URL}?{query}",
        headers={"User-Agent": "trading-research/1.0"},
    )
    try:
        with urlopen(request, timeout=60) as response:
            frame = pd.read_csv(io.BytesIO(response.read()))
    except HTTPError as error:
        raise RuntimeError(f"FRED request failed with HTTP {error.code}.") from error
    if frame.shape[1] < 2 or frame.columns[0] != "observation_date":
        raise RuntimeError(f"Unexpected FRED response for {series_id}.")
    result = frame.set_index("observation_date").iloc[:, 0]
    result.index = pd.to_datetime(result.index)
    return pd.to_numeric(result, errors="coerce").dropna().rename(series_id)


def sec_submissions(
    cik: str,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    """Download SEC submissions metadata for a company CIK."""
    agent = (user_agent or os.getenv("SEC_USER_AGENT", "")).strip()
    if not agent or "@" not in agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying name and email address."
        )
    normalized_cik = str(cik).strip().lstrip("0").zfill(10)
    payload = _json_request(
        SEC_SUBMISSIONS_URL.format(cik=normalized_cik),
        {},
        {"User-Agent": agent, "Accept-Encoding": "gzip, deflate"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"SEC returned an unexpected submissions response for {cik}.")
    return payload


def sec_company_facts(
    cik: str,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    """Download SEC XBRL company facts for a company CIK."""
    agent = (user_agent or os.getenv("SEC_USER_AGENT", "")).strip()
    if not agent or "@" not in agent:
        raise RuntimeError(
            "Set SEC_USER_AGENT to an identifying name and email address."
        )
    normalized_cik = str(cik).strip().lstrip("0").zfill(10)
    payload = _json_request(
        SEC_FACTS_URL.format(cik=normalized_cik),
        {},
        {"User-Agent": agent, "Accept-Encoding": "gzip, deflate"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"SEC returned an unexpected facts response for {cik}.")
    return payload
