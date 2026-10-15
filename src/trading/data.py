from collections.abc import Iterable
from pathlib import Path
from typing import Optional, Union
from urllib.request import Request, urlopen
import warnings

import pandas as pd
import yfinance as yf

ASSET_CLASS_KEYS = ("equities", "forex", "bonds", "commodities")


def _sanitize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    invalid = int((prices <= 0).sum().sum())
    if invalid:
        warnings.warn(
            f"Replaced {invalid} non-positive price observations with missing values; "
            "percentage-return backtests cannot represent zero or negative prices.",
            RuntimeWarning,
            stacklevel=2,
        )
        prices = prices.mask(prices <= 0)
    return prices


def sp500_symbols() -> list[str]:
    request = Request(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        headers={"User-Agent": "trading-research/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        table = pd.read_html(response.read())[0]
    symbols = table["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    if len(symbols) < 250:
        raise RuntimeError(f"S&P 500 source returned only {len(symbols)} symbols")
    return symbols


def configured_symbols(config: dict) -> list[str]:
    """Build a configured multi-asset research universe.

    Current index constituents are still a convenience source, not a
    point-in-time constituent database. ``historical_symbols`` is an explicit
    place to add delisted or failed securities supplied by a better provider.
    """
    symbols = list(config.get("symbols", []))
    if config.get("include_current_sp500", config.get("universe") == "sp500"):
        symbols.extend(sp500_symbols())
    symbols.extend(config.get("historical_symbols", []))
    for key in ASSET_CLASS_KEYS:
        symbols.extend(config.get("asset_classes", {}).get(key, []))
    symbols.extend(
        [
            config["benchmark"],
            config.get("nasdaq_benchmark", ""),
        ]
    )
    return list(dict.fromkeys(symbol for symbol in symbols if symbol))


def download_prices(
    symbols: Iterable[str],
    start: str,
    end: Optional[str] = None,
    cache_path: Union[str, Path] = "data/processed/prices.parquet",
) -> pd.DataFrame:
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise ValueError("At least one symbol is required")
    raw = yf.download(
        symbols,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no data")
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if isinstance(close, pd.Series):
        close = close.to_frame(name=symbols[0])
    close = close.sort_index().dropna(how="all")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = _sanitize_prices(close)
    if close.empty or close.isna().all().all():
        raise RuntimeError("Downloaded prices contain no usable observations")
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    close.to_parquet(path)
    return close


def coverage_report(prices: pd.DataFrame) -> pd.DataFrame:
    """Return first/last observation and count for every downloaded symbol."""
    records = []
    for symbol in prices.columns:
        observations = prices[symbol].dropna()
        records.append(
            {
                "symbol": symbol,
                "first_date": observations.index.min(),
                "last_date": observations.index.max(),
                "observations": int(observations.size),
                "available": not observations.empty,
            }
        )
    return pd.DataFrame.from_records(records).set_index("symbol")


def load_prices(path: Union[str, Path] = "data/processed/prices.parquet") -> pd.DataFrame:
    prices = pd.read_parquet(path)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices.sort_index()
    prices = _sanitize_prices(prices)
    if prices.empty:
        raise ValueError(f"No prices found in {path}")
    return prices
