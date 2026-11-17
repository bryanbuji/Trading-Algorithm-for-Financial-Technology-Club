# Strategy Overview

## Purpose

This is a weekly, long-only momentum research strategy. It ranks the configured
equity universe, holds a diversified subset of stronger names, and reduces
risk when volatility or the broad market drawdown rises. It is a backtest, not
a live trading system or a promise of returns.

## Weekly decision process

1. **Build the eligible universe.** Yahoo Finance adjusted prices are requested
   for configured ETFs and every ticker found in a free community S&P 500
   history, plus the current S&P 500 roster. A dated membership mask allows
   historical names into the ranking only while they were constituents. The
   community file currently ends on 2026-06-02; the last snapshot is carried
   forward. The live roster is applied only to a price bar dated today.
   Changes during that gap may be inaccurate. Yahoo may not return usable
   history for every past constituent or its delisting event.
2. **Measure momentum.** For each symbol, calculate the return from roughly six
   months ago through one month ago (`126` trading days lookback, skipping the
   latest `21` days). This skips the short-term reversal-prone period.
3. **Filter and rank.** Drop symbols without enough price history, with
   non-positive estimated volatility, or more than 15% below their 63-day
   trailing high. Rank the rest by momentum and select up to the top 20.
4. **Set portfolio exposure.** The target starts at 100%. If SPY is 10% below
   its running high, exposure starts to fall linearly, reaching the 25% floor
   at a 25% SPY drawdown. Volatility targeting can lower exposure further to
   target 20% annualized portfolio volatility.
5. **Size positions.** Allocate inversely to each selected asset's 63-day
   annualized volatility, while capping each position at 5%. The allocator
   redistributes weight removed by caps. If fewer than 20 candidates qualify,
   the unused portion remains in cash; SPY is the fallback when no candidates
   qualify.
6. **Execute and account.** Signals use Friday data and are delayed by one
   trading session before the backtest changes holdings. The ledger deducts
   configured commission, spread, slippage, and market-impact estimates.

## Key settings

`config.yaml` controls the universe, 20-stock target, six-month lookback,
one-month skip, volatility window, position cap, exposure controls, costs,
and rebalancing frequency. The conservative and aggressive profiles change
some of these values. The optional ML workflow replaces momentum ranks with
walk-forward return predictions; it uses the same sizing and exposure logic.

## Data and interpretation limits

The default source is free Yahoo Finance history through `yfinance`, which is
an unofficial research interface and may throttle requests, omit delisted
securities, or revise adjusted history. Historical membership comes from a
community reconstruction with stated gaps, while Yahoo lacks complete
delisting coverage. Do not interpret the result as entirely survivorship-bias
free. Yahoo data and this code are for educational research; check Yahoo's
terms for data use. See [README.md](README.md) for download instructions and
[AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) for known limitations.

Momentum, stops, volatility scaling, costs, and drawdown rules may all reduce
returns. Compare against SPY and simpler baselines on untouched periods before
changing settings. A larger universe does not guarantee better performance.
