"""Download optional Alpha Vantage, FRED, and SEC research data."""

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from trading.open_data import (
    fred_series,
    merge_alpha_vantage_prices,
    sec_company_facts,
    sec_submissions,
)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--merge-alpha-symbol",
    action="append",
    default=[],
    help="Add Alpha Vantage history to the existing Yahoo prices cache.",
)
parser.add_argument(
    "--prices-cache",
    type=Path,
    default=root / "data" / "processed" / "prices.parquet",
)
parser.add_argument(
    "--alpha-data-dir",
    type=Path,
    default=root / "data" / "alpha_vantage",
)
parser.add_argument("--fred-series", action="append", default=[])
parser.add_argument("--sec-cik", action="append", default=[])
args = parser.parse_args()

output = root / "data" / "external"
output.mkdir(parents=True, exist_ok=True)

if args.merge_alpha_symbol:
    if not args.prices_cache.exists():
        raise SystemExit(f"Yahoo prices cache does not exist: {args.prices_cache}")
    yahoo_prices = pd.read_parquet(args.prices_cache)
    merged = merge_alpha_vantage_prices(
        yahoo_prices,
        args.merge_alpha_symbol,
        cache_dir=args.alpha_data_dir,
    )
    args.prices_cache.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(args.prices_cache)
    print(
        f"Merged {len(args.merge_alpha_symbol)} Alpha Vantage symbol(s) into "
        f"{args.prices_cache}"
    )

for series_id in args.fred_series:
    series = fred_series(series_id)
    series.to_csv(output / f"fred_{series_id}.csv", header=True)
    print(f"Saved FRED series {series_id}")

for cik in args.sec_cik:
    submissions = sec_submissions(cik)
    facts = sec_company_facts(cik)
    (output / f"sec_submissions_{cik}.json").write_text(
        json.dumps(submissions, indent=2)
    )
    (output / f"sec_companyfacts_{cik}.json").write_text(
        json.dumps(facts, indent=2)
    )
    print(f"Saved SEC submissions and company facts for CIK {cik}")

if not (args.merge_alpha_symbol or args.fred_series or args.sec_cik):
    parser.error(
        "Specify at least one --merge-alpha-symbol, --fred-series, or --sec-cik."
    )
