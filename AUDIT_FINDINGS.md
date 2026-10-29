# Repository Audit Findings

## Corrections made

- **Negative equity:** terminal missing-price liquidation produced a -100% asset return, then subtracted trading costs, allowing portfolio returns below -100% and negative equity. Long-only runs now reject negative or over-100% weights and floor a daily loss at -100%.
- **Execution alignment:** transaction costs and trade rows were previously placed on signal dates, while weights were lagged for returns. The backtest now shifts holdings to the execution date, charges costs there, and earns daily close-to-close returns after the fill. Daily closes approximate the next-session fill; this is not an open-price execution model.
- **Rule-strategy look-ahead:** volatility targeting used the final volatility observation for every historical signal. It now estimates portfolio volatility using data only through each signal date.
- **ML data/label errors:** expanding training windows included labels whose 21-bar future return reached into the prediction date, and daily-mode resampling inserted calendar weekends. Training now purges the most recent 21 bars; daily mode keeps trading-session rows. ML prices no longer forward-fill a terminal price indefinitely, which had generated artificial zero-return labels after a symbol disappeared.
- **Universe and notebook output:** the default config no longer downloads current S&P 500 members for use over past history and omits front-month futures from ordinary percentage-return logic. Price and coverage tables now show formatted samples; notebooks save complete, date-formatted trade ledgers to ignored CSV files rather than rendering every row.
- **Documentation:** removed fixed cache dimensions and stale performance tables, reduced repeated run instructions, and corrected the ML model description and universe limitations.

## Remaining material limitations

The configured ETF list and the small failed-equity list are hand-selected and do not include a point-in-time ETF membership/security master or complete delisting returns. Disappearance on the fifth consecutive missing observation is represented as a total loss, not an observed delisting event; interior missing prices are forward-filled and can hide stale marks. The trade ledger estimates notional and realized P/L from executed weight changes; it is not a cash-and-shares accounting engine. Close-only prices cannot model opening fills, spreads, market impact by volume, corporate-action cash, or exchange holidays precisely.

The momentum lookback, skip, stop, volatility sizing, and risk profiles have no nested walk-forward parameter selection or untouched reported holdout. The aggressive profile is an exploratory setting; historical profile comparisons are not evidence of out-of-sample superiority. The ML correlation likewise uses sparse predictions with overlapping target windows and should be treated descriptively.

## Recommended next steps

1. For stock-level results, license CRSP US Stock or Norgate data with effective-dated security identifiers, historical constituent membership, corporate actions, and delisting returns. Do not merge on ticker alone; map stable security IDs and membership intervals.
2. Add a provider adapter that validates unique dates, sorted timestamps, price units/currency, split/dividend adjustments, missingness, and return outliers. Save an immutable source/date/config manifest beside every Parquet cache.
3. Add purged/embargoed nested walk-forward selection, report a final untouched period, and compare against SPY and a simple ETF momentum baseline under the same costs.
4. Replace target-weight P/L estimates with cash, shares, fill prices, corporate-action events, and mark-to-market accounting before using trade-level cash results as an audit trail.

CRSP describes historical inactive-security and delisting data in its [US Stock database overview](https://www.crsp.org/research/crsp-us-stock-databases-2025-layout/). Norgate documents historical constituents and delisted securities in its [data content tables](https://norgatedata.com/data-content-tables/). Both require checking current access and licensing terms.
