from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, Union
import time
import warnings
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

ASSET_CLASS_KEYS = ("equities", "forex", "bonds", "commodities")
SP500_HISTORY_URL = (
    "https://raw.githubusercontent.com/thuningxu/sp500nq100/main/"
    "sp500_components_history.csv"
)


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
        table = pd.read_html(BytesIO(response.read()))[0]
    symbols = table["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    if len(symbols) < 250:
        raise RuntimeError(f"S&P 500 source returned only {len(symbols)} symbols")
    return symbols


def sp500_history_snapshots() -> pd.DataFrame:
    """Fetch free, dated S&P 500 membership snapshots maintained on GitHub."""
    request = Request(SP500_HISTORY_URL, headers={"User-Agent": "trading-research/1.0"})
    with urlopen(request, timeout=30) as response:
        frame = pd.read_csv(BytesIO(response.read()))
    columns = {str(column).strip().lower(): column for column in frame.columns}
    date_column = columns.get("date")
    tickers_column = columns.get("tickers")
    if date_column is None or tickers_column is None:
        raise ValueError("S&P 500 history source must have date and tickers columns")
    result = frame[[date_column, tickers_column]].copy()
    result.columns = ["date", "tickers"]
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result["tickers"] = result["tickers"].fillna("").map(
        lambda value: [
            symbol.strip().replace(".", "-")
            for symbol in str(value).split(",")
            if symbol.strip()
        ]
    )
    result = result.dropna(subset=["date"]).sort_values("date")
    if result.empty or result["date"].duplicated().any():
        raise ValueError("S&P 500 history source has no rows or duplicate snapshot dates")
    if result["tickers"].map(len).max() < 400:
        raise ValueError("S&P 500 history source returned incomplete constituent snapshots")
    return result.set_index("date")


def sp500_membership_mask(
    dates: pd.DatetimeIndex,
    symbols: pd.Index,
    snapshots: pd.DataFrame,
    current_symbols: Iterable[str],
    current_as_of: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Create a date-aligned membership mask; non-index instruments stay eligible."""
    history_symbols = set(current_symbols)
    for tickers in snapshots["tickers"]:
        history_symbols.update(tickers)
    state = pd.DataFrame(False, index=snapshots.index, columns=sorted(history_symbols))
    for date, row in snapshots.iterrows():
        tickers = [symbol for symbol in row["tickers"] if symbol in state.columns]
        state.loc[date, tickers] = True

    dates = pd.DatetimeIndex(dates)
    current_as_of = pd.Timestamp(current_as_of or pd.Timestamp.today().normalize())
    if len(dates) and dates.max() >= current_as_of and current_symbols:
        state.loc[current_as_of] = False
        active = [symbol for symbol in current_symbols if symbol in state.columns]
        state.loc[current_as_of, active] = True
    state = state.sort_index().reindex(dates, method="ffill").fillna(False).astype(bool)

    mask = pd.DataFrame(True, index=dates, columns=symbols)
    historical_columns = mask.columns.intersection(state.columns)
    mask.loc[:, historical_columns] = state.reindex(columns=historical_columns)
    return mask


def configured_symbols(
    config: dict,
    historical_snapshots: Optional[pd.DataFrame] = None,
    current_sp500: Optional[list[str]] = None,
) -> list[str]:
    """Build a configured multi-asset research universe.

    Current index constituents are still a convenience source, not a
    point-in-time constituent database. ``historical_symbols`` is an explicit
    place to add delisted or failed securities supplied by a better provider.
    """
    symbols = list(config.get("symbols", []))
    if config.get("include_historical_sp500", False):
        if historical_snapshots is None:
            historical_snapshots = sp500_history_snapshots()
        symbols.extend(
            symbol
            for tickers in historical_snapshots["tickers"]
            for symbol in tickers
        )
    if config.get("include_current_sp500", config.get("universe") == "sp500"):
        symbols.extend(current_sp500 if current_sp500 is not None else sp500_symbols())
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
    batch_size: int = 25,
    pause_seconds: float = 1.0,
) -> pd.DataFrame:
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise ValueError("At least one symbol is required")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    batches = [symbols[offset : offset + batch_size] for offset in range(0, len(symbols), batch_size)]
    frames = []
    for position, batch in enumerate(batches):
        try:
            raw = yf.download(
                batch,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                group_by="column",
                threads=True,
            )
        except Exception as error:
            warnings.warn(f"Yahoo batch {position + 1} failed: {error}", RuntimeWarning)
            raw = pd.DataFrame()
        if not raw.empty:
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw.get("Close")
            if isinstance(close, pd.Series):
                close = close.to_frame(name=batch[0])
            if isinstance(close, pd.DataFrame):
                frames.append(close)
        if position + 1 < len(batches) and pause_seconds > 0:
            time.sleep(pause_seconds)
    if not frames:
        raise RuntimeError("Yahoo Finance returned no data")
    close = pd.concat(frames, axis=1).loc[:, lambda frame: ~frame.columns.duplicated()]
    close = close.sort_index().dropna(how="all")
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = _sanitize_prices(close)
    if close.empty or close.isna().all().all():
        raise RuntimeError("Downloaded prices contain no usable observations")
    missing = sorted(set(symbols).difference(close.columns))
    if missing:
        warnings.warn(
            f"Yahoo returned no prices for {len(missing)} of {len(symbols)} symbols; "
            f"examples: {', '.join(missing[:12])}",
            RuntimeWarning,
        )
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


def load_configured_market_data(
    config: Any,
    project_root: Union[str, Path],
    refresh_yahoo: bool = False,
) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """Load or refresh the Yahoo adjusted-price cache."""
    root = Path(project_root)
    provider = config.values.get("data_provider", "yahoo")
    if provider != "yahoo":
        raise ValueError("data_provider must be 'yahoo'")

    cache_path = root / "data" / "processed" / "prices.parquet"
    if refresh_yahoo:
        snapshots = (
            sp500_history_snapshots()
            if config.values.get("include_historical_sp500", False)
            else None
        )
        current_sp500 = (
            sp500_symbols()
            if config.values.get("include_current_sp500", False)
            or config.values.get("universe") == "sp500"
            else []
        )
        prices = download_prices(
            configured_symbols(config.values, snapshots, current_sp500),
            config["start_date"],
            config.values.get("end_date"),
            cache_path,
        )
        membership = None
        if snapshots is not None:
            membership = sp500_membership_mask(
                prices.index, prices.columns, snapshots, current_sp500
            )
            membership.to_parquet(root / "data" / "processed" / "universe_membership.parquet")
        alpha_symbols = config.values.get("alpha_vantage_symbols", [])
        if alpha_symbols:
            from trading.open_data import merge_alpha_vantage_prices

            import os

            if not os.environ.get("ALPHAVANTAGE_API_KEY"):
                raise RuntimeError(
                    "alpha_vantage_symbols is configured but ALPHAVANTAGE_API_KEY is missing"
                )
            prices = merge_alpha_vantage_prices(
                prices,
                alpha_symbols,
                cache_dir=root / "data" / "alpha_vantage",
            )
            prices.to_parquet(cache_path)
    else:
        prices = load_prices(cache_path)
        membership_path = root / "data" / "processed" / "universe_membership.parquet"
        membership = (
            pd.read_parquet(membership_path).reindex(index=prices.index, columns=prices.columns)
            if membership_path.exists()
            else None
        )
        if membership is not None:
            membership = membership.fillna(False).astype(bool)
    return prices, membership
