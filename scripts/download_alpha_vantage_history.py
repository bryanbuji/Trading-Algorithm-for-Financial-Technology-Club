"""Download and cache Alpha Vantage daily adjusted history by ticker."""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from trading.alpha_vantage_history import (
    AlphaVantageHistoryDownloader,
    RequestLedger,
    load_ticker_requests,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers-file",
        type=Path,
        required=True,
        help="Text list (one ticker per line) or CSV with symbol, optional api_symbol/status columns.",
    )
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "alpha_vantage")
    parser.add_argument(
        "--listing-status-date",
        help="Optional YYYY-MM-DD date passed to LISTING_STATUS when delisted rows are present.",
    )
    parser.add_argument("--max-calls-per-minute", type=int, default=5)
    parser.add_argument("--max-calls-per-day", type=int, default=25)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    if args.listing_status_date:
        try:
            datetime.strptime(args.listing_status_date, "%Y-%m-%d")
        except ValueError:
            parser.error("--listing-status-date must use YYYY-MM-DD")

    try:
        tickers = load_ticker_requests(args.tickers_file)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if not tickers:
        parser.error("ticker input contains no symbols")

    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    limiter = RequestLedger(
        args.data_dir / ".request_history.json",
        max_calls_per_minute=args.max_calls_per_minute,
        max_calls_per_day=args.max_calls_per_day,
    )
    downloader = AlphaVantageHistoryDownloader(
        api_key,
        args.data_dir,
        limiter=limiter,
        max_retries=args.max_retries,
        listing_status_date=args.listing_status_date,
    )
    stats = downloader.download(tickers)
    print(
        "Complete: "
        f"{stats['saved']} saved, {stats['cached']} already cached, "
        f"{stats['failed']} failed, {stats['deferred']} deferred."
    )
    print(f"Errors: {downloader.error_log}")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
