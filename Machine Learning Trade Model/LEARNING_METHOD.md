# Machine-learning method

The optional trade model is a **supervised learning** model. It learns from
historical examples where:

- **Features:** lagged momentum, volatility, relative strength versus the
  benchmark, and benchmark volatility.
- **Target:** the subsequent 21-period price return for each symbol.
- **Prediction:** an estimated future return used to rank candidate positions.

The implementation uses ordinary **multiple linear regression** from
`sklearn.linear_model.LinearRegression`. It estimates one linear relationship
between the feature values and future returns during each chronological
walk-forward training step. It is not a neural network, clustering model, or
reinforcement-learning system.

Training is walk-forward: each prediction is generated using observations
strictly earlier than its prediction date. This reduces look-ahead leakage, but
does not eliminate data limitations such as survivorship bias, missing
delisted securities, or unstable relationships in financial markets.

The model is a research component, not a claim that returns are reliably
predictable. Compare its out-of-sample results with the rules-based strategy
and buy-and-hold benchmark, including transaction costs.
