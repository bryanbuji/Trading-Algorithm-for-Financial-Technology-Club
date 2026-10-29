# Machine-learning method

The optional trade model is a **supervised learning** model. It learns from
historical examples where:

- **Features:** lagged momentum, volatility, relative strength versus the
  benchmark, and benchmark volatility.
- **Target:** the subsequent 21-bar price return at the configured sampling
  frequency (for example, 21 weekly bars with `W-FRI`).
- **Prediction:** an estimated future return used to rank candidate positions.

The implementation uses ordinary **multiple linear regression** from
`sklearn.linear_model.LinearRegression`. It estimates one linear relationship
between the feature values and future returns during each chronological
walk-forward training step. It is not a neural network, clustering model, or
reinforcement-learning system.

Training is walk-forward and purged: the last 21 bars before a prediction are
excluded from fitting because their forward-return labels overlap the
prediction date. This reduces label leakage, but does not eliminate data
limitations such as survivorship bias, missing delisted securities, repeated
testing, or unstable relationships in financial markets. Target windows for
different predictions still overlap, so prediction/target correlation is a
descriptive diagnostic rather than an independent-observation test.

The model is a research component, not a claim that returns are reliably
predictable. Compare its out-of-sample results with the rules-based strategy
and buy-and-hold benchmark, including transaction costs.
