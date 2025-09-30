from itertools import product
from pathlib import Path

import pandas as pd

from intraday_trend_strategy import (
    load_series,
    simulate,
    performance,
    run_backtest,
)

DATA_PATH = Path("5-min-SOL.csv")

# Parameter grids chosen to explore slightly wider behaviour for SOL's volatility profile
ENTRY_BUFFERS = [0.992, 0.994, 0.996, 0.998]
ENTRY_LEVERAGES = [1.0, 1.2, 1.4]
TRAILING_STOPS = [0.08, 0.10, 0.12]
COOLDOWN_BARS = [144, 288, 432]
PANIC_THRESHOLDS = [-0.09, -0.07, -0.05]

MAX_DRAWDOWN_LIMIT = -0.35
OUTPUT_PREFIX = "intraday_trend_sol_opt"


def main() -> None:
    close = load_series(DATA_PATH)

    results = []
    combos = list(product(ENTRY_BUFFERS, ENTRY_LEVERAGES, TRAILING_STOPS, COOLDOWN_BARS, PANIC_THRESHOLDS))
    total = len(combos)
    for idx, (buf, lev, stop, cooldown, panic) in enumerate(combos, start=1):
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
    results_df.to_csv("sol_optimization_grid.csv", index=False)

    eligible = results_df[results_df["MaxDrawdown"] >= MAX_DRAWDOWN_LIMIT]
    if eligible.empty:
        best_row = results_df.sort_values("FinalMultiple", ascending=False).iloc[0]
    else:
        best_row = eligible.sort_values("FinalMultiple", ascending=False).iloc[0]

    print("Best parameters:")
    print(best_row[["entry_buffer", "entry_leverage", "trailing_stop", "cooldown", "panic_threshold"]])
    print("Stats:")
    print(best_row[["CAGR", "AnnualVol", "Sharpe", "Sortino", "MaxDrawdown", "FinalMultiple"]])

    run_backtest(
        DATA_PATH,
        output_prefix=OUTPUT_PREFIX,
        entry_buffer=best_row["entry_buffer"],
        entry_leverage=best_row["entry_leverage"],
        trailing_stop=best_row["trailing_stop"],
        cooldown_bars=int(best_row["cooldown"]),
        panic_threshold=best_row["panic_threshold"],
    )


if __name__ == "__main__":
    main()
