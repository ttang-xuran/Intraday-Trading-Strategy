from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

from intraday_trend_strategy import (
    load_series,
    simulate,
    performance,
    run_backtest,
    DEFAULT_ENTRY_BUFFER,
    DEFAULT_ENTRY_LEVERAGE,
    DEFAULT_TRAILING_STOP,
    DEFAULT_COOLDOWN_BARS,
    DEFAULT_PANIC_THRESHOLD,
)

DATA_PATH = Path("5-min-ETH.csv")

# Parameter grids
ENTRY_BUFFERS = [0.993, 0.995, 0.998]
ENTRY_LEVERAGES = [1.1, 1.3, 1.5]
TRAILING_STOPS = [0.10, 0.12]
COOLDOWN_BARS = [144, 288]
PANIC_THRESHOLDS = [-0.09, -0.07]

MAX_DRAWDOWN_LIMIT = -0.40  # target <= 40% drawdown
OUTPUT_PREFIX = "intraday_trend_eth_opt"


close = load_series(DATA_PATH)

results = []
total = len(ENTRY_BUFFERS) * len(ENTRY_LEVERAGES) * len(TRAILING_STOPS) * len(COOLDOWN_BARS) * len(PANIC_THRESHOLDS)
for idx, (buf, lev, stop, cooldown, panic) in enumerate(
    product(ENTRY_BUFFERS, ENTRY_LEVERAGES, TRAILING_STOPS, COOLDOWN_BARS, PANIC_THRESHOLDS),
    start=1,
):
    if idx % 10 == 0 or idx == total:
        print(f"Evaluating set {idx}/{total}...")
    df = simulate(
        close,
        entry_buffer=buf,
        entry_leverage=lev,
        trailing_stop=stop,
        cooldown_bars=cooldown,
        panic_threshold=panic,
    )
    stats = performance(df["return"])
    stats.update(
        {
            "entry_buffer": buf,
            "entry_leverage": lev,
            "trailing_stop": stop,
            "cooldown": cooldown,
            "panic_threshold": panic,
        }
    )
    results.append(stats)

results_df = pd.DataFrame(results)
results_df.to_csv("eth_optimization_grid.csv", index=False)

# Filter by drawdown constraint
eligible = results_df[results_df["MaxDrawdown"] >= MAX_DRAWDOWN_LIMIT]
if eligible.empty:
    best_row = results_df.sort_values("FinalMultiple", ascending=False).iloc[0]
else:
    best_row = eligible.sort_values("FinalMultiple", ascending=False).iloc[0]

print("Best parameters:")
print(best_row[["entry_buffer", "entry_leverage", "trailing_stop", "cooldown", "panic_threshold"]])
print("Stats:")
print(best_row[["CAGR", "AnnualVol", "Sharpe", "Sortino", "MaxDrawdown", "FinalMultiple"]])

# Run full backtest with best parameters and write CSV outputs
run_backtest(
    DATA_PATH,
    output_prefix=OUTPUT_PREFIX,
    entry_buffer=best_row["entry_buffer"],
    entry_leverage=best_row["entry_leverage"],
    trailing_stop=best_row["trailing_stop"],
    cooldown_bars=int(best_row["cooldown"]),
    panic_threshold=best_row["panic_threshold"],
)
