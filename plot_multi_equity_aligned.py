from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

SERIES = [
    (Path("intraday_trend_returns.csv"), "BTC Trend (default)"),
    (Path("intraday_trend_eth_opt_returns.csv"), "ETH Trend (optimized)"),
    (Path("intraday_trend_sol_opt_returns.csv"), "SOL Trend (optimized)"),
]
START_CAPITAL = 100_000
OUTPUT_PNG = Path("intraday_trend_multi_equity_aligned.png")
OUTPUT_CSV = Path("intraday_trend_multi_equity_aligned.csv")


def load_returns(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["iso_time"])
    df.sort_values("iso_time", inplace=True)
    df["return"] = df["return"].astype(float).fillna(0.0)
    df.set_index("iso_time", inplace=True)
    return df


def main() -> None:
    datasets = []
    indices = []

    for path, label in SERIES:
        if not path.exists():
            print(f"Skipping {label}: {path} not found")
            continue
        df = load_returns(path)
        if df.empty:
            print(f"Skipping {label}: no data available")
            continue
        datasets.append((label, df))
        indices.append(df.index)

    if len(datasets) < 2:
        print("Not enough series to plot.")
        return

    common_index = indices[0]
    for idx in indices[1:]:
        common_index = common_index.intersection(idx)

    common_index = common_index.sort_values()

    if common_index.empty:
        print("No overlapping dates found across series.")
        return

    capital_df = pd.DataFrame(index=common_index)

    for label, df in datasets:
        aligned = df.loc[common_index]
        equity = (1.0 + aligned["return"]).cumprod()
        capital = START_CAPITAL * equity / equity.iloc[0]
        capital_df[label] = capital

    capital_df.reset_index(names="iso_time").to_csv(OUTPUT_CSV, index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    for label in capital_df.columns:
        ax.plot(capital_df.index, capital_df[label], label=label)

    start, end = capital_df.index.min(), capital_df.index.max()
    ax.set_title(
        f"Intraday Trend Capital Curves (00K start, shared history)\n{start.date()} to {end.date()}"
    )
    ax.set_ylabel("Portfolio Value (USD)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.0f}"))

    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=140)
    print(f"Saved aligned capital curve to {OUTPUT_PNG}")
    print(f"Aligned series exported to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
