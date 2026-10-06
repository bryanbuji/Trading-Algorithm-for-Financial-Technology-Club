from pathlib import Path
from typing import Iterable, Optional, Union
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf


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
    if close.empty or close.isna().all().all():
        raise RuntimeError("Downloaded prices contain no usable observations")
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    close.to_parquet(path)
    return close


def load_prices(path: Union[str, Path] = "data/processed/prices.parquet") -> pd.DataFrame:
    prices = pd.read_parquet(path)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices.sort_index()
    if prices.empty:
        raise ValueError(f"No prices found in {path}")
    return prices
