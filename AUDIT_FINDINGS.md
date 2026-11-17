# Repository Audit Findings

## Corrections made

- **Negative equity:** terminal missing-price liquidation produced a -100% asset return, then subtracted trading costs, allowing portfolio returns below -100% and negative equity. Long-only runs now reject negative or over-100% weights and floor a daily loss at -100%.
- **Execution alignment:** transaction costs and trade rows were previously placed on signal dates, while weights were lagged for returns. The backtest now shifts holdings to the execution date, charges costs there, and earns daily close-to-close returns after the fill. Daily closes approximate the next-session fill; this is not an open-price execution model.
- **Rule-strategy look-ahead:** volatility targeting used the final volatility observation for every historical signal. It now estimates portfolio volatility using data only through each signal date.
- **ML data/label errors:** expanding training windows included labels whose 21-bar future return reached into the prediction date, and daily-mode resampling inserted calendar weekends. Training now purges the most recent 21 bars; daily mode keeps trading-session rows. ML prices no longer forward-fill a terminal price indefinitely, which had generated artificial zero-return labels after a symbol disappeared.
- **Universe and notebook output:** the default Yahoo workflow downloads current and historical S&P 500 tickers in batches, plus configured ETFs and explicit failed tickers. It saves a point-in-time membership mask from free community snapshots and targets 20 holdings capped at 5% each. Price and coverage tables show formatted samples; notebooks save complete, date-formatted trade ledgers to ignored CSV files rather than rendering every row.
- **Documentation:** removed fixed cache dimensions and stale performance tables, reduced repeated run instructions, and corrected the ML model description and universe limitations.

## Remaining material limitations

The free community membership history is reconstructed and currently ends on 2026-06-02. The latest historical state is carried forward to the latest Yahoo date and then reconciled to today's S&P roster, leaving membership changes in that gap unresolved. Yahoo does not return all historical failed securities, stable company identifiers, or complete delisting returns; recycled tickers can point to the wrong security. Disappearance on the fifth consecutive missing observation is represented as a total loss, not an observed delisting return; interior missing prices are forward-filled and can hide stale marks. The trade ledger estimates notional and realized P/L from executed weight changes; it is not a cash-and-shares accounting engine. Close-only prices cannot model opening fills, spreads, market impact by volume, corporate-action cash, or exchange holidays precisely.

After refreshing 1,274 Yahoo symbols and applying the historical membership mask, the backtest reports 11.2% annualized return, 0.64 Sharpe, and -32.8% maximum drawdown; SPY reports 14.9%, 0.92, and -33.7%, respectively. From 2023 onward, the strategy returned 13.7% annualized versus SPY at 21.7%. Under higher assumed costs, strategy returns were near flat at 0.5% annualized. The causal look-ahead mutation check passes, but this does not resolve the Yahoo and membership-source coverage gaps. The strategy still trails SPY by a wide margin in return and Sharpe.

The momentum lookback, skip, stop, volatility sizing, and risk profiles have no nested walk-forward parameter selection or untouched reported holdout. The aggressive profile is an exploratory setting; historical profile comparisons are not evidence of out-of-sample superiority. The ML correlation likewise uses sparse predictions with overlapping target windows and should be treated descriptively.

## Recommended next steps

1. If evaluating point-in-time stock selection with free sources, validate community constituent snapshots against source change logs and independently audit Yahoo symbol history, ticker changes, missing dates, and delistings.
2. Save an immutable source/date/config manifest beside each refreshed cache.
3. Add purged/embargoed nested walk-forward selection, reserve a final untouched period, and compare against SPY and a simple ETF momentum baseline under the same costs. Do not tune to the currently weak SPY comparison.
4. Replace target-weight P/L estimates with cash, shares, fill prices, corporate-action events, and mark-to-market accounting before using trade-level cash results as an audit trail.
