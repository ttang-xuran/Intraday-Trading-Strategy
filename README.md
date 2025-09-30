# Intraday Trend Strategy

This repository contains research code for an intraday cryptocurrency breakout strategy that trades liquid pairs such as BTC, ETH, and SOL on 5-minute bars. The tooling covers data collection from Bitget, signal generation, parameter sweeps, and basic reporting artifacts so you can reproduce the results or adapt the logic to your own venue.

## Prerequisites

- Python 3.10 or newer (matches the project tooling guidance).
- A virtual environment is recommended: `python3 -m venv .venv && source .venv/bin/activate`.
- Install dependencies used throughout the scripts:
  ```bash
  pip install pandas numpy matplotlib requests python-dotenv
  ```
- Export Bitget API credentials before running the data downloaders:
  ```bash
  export BITGET_API_KEY=...
  export BITGET_SECRET=...
  export BITGET_PASSPHRASE=...
  ```
  The download utilities import the authenticated REST client from `Test market and limit orders (successful).py`, so the credentials only need to be configured in one place.

## Data sources

Two helper scripts backfill 5-minute spot candles directly from Bitget and append to local CSV files:

- `download_sol_5min.py` requests historical SOL/USDT data in configurable batches, de-duplicates rows, and writes the results to `5-min-SOL.csv`. It throttles requests, retries on rate limits, and resumes from the earliest timestamp that already exists on disk to simplify incremental refreshes.
- `download_eth_5min.py` mirrors the SOL workflow for ETH/USDT, persisting data to `5-min-ETH.csv` and honoring `MAX_BATCHES`/sleep controls via environment variables.

Both scripts can be executed with `python download_sol_5min.py` or `python download_eth_5min.py` after credentials are set, and they will report how many new rows were added to the CSV.

## Strategy logic

`intraday_trend_strategy.py` houses the core backtest that the SOL and ETH runs build upon:

- Loads 5-minute closes from a CSV (defaulting to BTC) and computes 2-, 3.5-, and 5-day simple moving averages plus a rolling 6-day high using 288 bars per day.
- Goes long when price holds above the mid/slow averages and breaks through the buffered high, applying configurable leverage.
- Monitors the position with a trailing stop, moving-average breakdown checks, and a large down-bar “panic” filter. When an exit triggers, the strategy enters a cooldown window before re-arming.
- Applies 5 bps of fees per unit of turnover and resamples returns/exposure to daily series. The script writes `_returns.csv`, `_exposure.csv`, and `_stats.csv` files for the chosen output prefix.

Run a standalone backtest with, for example:
```bash
python intraday_trend_strategy.py --data 5-min-SOL.csv --output-prefix intraday_trend_sol
```

## Parameter optimisation

`optimize_sol_strategy.py` demonstrates a brute-force sweep tailored to SOL’s volatility. It iterates through grids of entry buffers, leverage, trailing-stop widths, cooldowns, and panic thresholds; filters by maximum drawdown; then selects the highest final equity multiple that satisfies the constraint. The script exports the full parameter grid to `sol_optimization_grid.csv`, prints the best configuration, and re-runs the backtest with an `intraday_trend_sol_opt` prefix so the standard CSV outputs are available for comparisons.

An ETH variant (`optimize_eth_strategy.py`) provides a narrower grid centered around the default BTC parameters and writes `eth_optimization_grid.csv` alongside its `_returns`, `_exposure`, and `_stats` artifacts.

## Performance artifacts

Two ready-made outputs help you review prior runs:

- `strategy_summary.csv` collects headline metrics—CAGR, annualized volatility, Sharpe, drawdown, hit rate, and turnover—from a representative backtest. You can regenerate a similar table by loading the per-run `_stats.csv` files into pandas and exporting the aggregate view once you finish a new sweep.
- `intraday_trend_sol_equity.png` is produced by `plot_sol_equity.py`, which plots cumulative equity curves for both the default SOL configuration and the optimized parameter set using the corresponding `_returns.csv` files.

After you rerun the backtests, refresh the equity comparison with:
```bash
python plot_sol_equity.py
```

## Typical workflow

1. **Download candles:** Populate `5-min-<TICKER>.csv` using the Bitget download scripts.
2. **Run the baseline backtest:** Execute `intraday_trend_strategy.py` with the desired dataset and output prefix.
3. **Sweep parameters (optional):** Use the optimisation scripts to search for better drawdown/return trade-offs; inspect `*_opt_stats.csv` for the resulting metrics.
4. **Review performance:** Plot equity curves or combine the `_stats.csv` files into a `strategy_summary.csv` style report.

With these components, you can iteratively update the dataset, validate changes to the breakout logic, and track how refinements affect risk-adjusted returns.

