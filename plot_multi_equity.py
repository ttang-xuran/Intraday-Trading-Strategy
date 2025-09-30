from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

SERIES = [
    (Path("intraday_trend_returns.csv"), "BTC"),
    (Path("intraday_trend_eth_returns.csv"), "ETH"),
    (Path("intraday_trend_sol_returns.csv"), "SOL"),
]
OUTPUT_IMAGE = Path("intraday_trend_multi_equity.png")
START_CAPITAL = 100_000


def load_capital_series(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["iso_time"])
    if df.empty:
        return df
    df.sort_values("iso_time", inplace=True)
    df["return"] = df["return"].astype(float).fillna(0.0)
    df["equity"] = (1.0 + df["return"]).cumprod()
    initial_equity = df["equity"].iloc[0]
    df["capital"] = df["equity"] / initial_equity * START_CAPITAL
    return df[["iso_time", "capital"]]


def main() -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    any_plotted = False

    for path, label in SERIES:
        if not path.exists():
            print(f"Skipping {label}: {path} not found")
            continue
        df = load_capital_series(path)
        if df.empty:
            print(f"Skipping {label}: no data available")
            continue
        ax.plot(df["iso_time"], df["capital"], label=f"{label} Trend")
        any_plotted = True

    if not any_plotted:
        print("No series available; aborting plot.")
        return

    ax.set_title("Intraday Trend Strategy Capital Curves (00K start)")
    ax.set_ylabel("Portfolio Value (USD)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.0f}"))

    fig.tight_layout()
    fig.savefig(OUTPUT_IMAGE, dpi=140)
    print(f"Saved capital curve comparison to {OUTPUT_IMAGE}")


if __name__ == "__main__":
    main()
