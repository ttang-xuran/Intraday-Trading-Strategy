from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

SERIES = [
    (Path("intraday_trend_returns.csv"), "BTC"),
    (Path("intraday_trend_eth_returns.csv"), "ETH"),
    (Path("intraday_trend_sol_returns.csv"), "SOL"),
]
OUTPUT_IMAGE = Path("intraday_trend_multi_equity_2025.png")
START_DATE = pd.Timestamp("2025-01-01", tz="UTC")
END_DATE = pd.Timestamp("2026-01-01", tz="UTC")


def load_equity(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["iso_time"])
    df.sort_values("iso_time", inplace=True)
    df["return"] = df["return"].astype(float).fillna(0.0)
    df["equity"] = (1.0 + df["return"]).cumprod()
    mask = (df["iso_time"] >= START_DATE) & (df["iso_time"] < END_DATE)
    df = df.loc[mask]
    if df.empty:
        return df
    df["equity"] = df["equity"] / df["equity"].iloc[0]
    return df


def main() -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    any_plotted = False

    for path, label in SERIES:
        if not path.exists():
            print(f"Skipping {label}: {path} not found")
            continue
        df = load_equity(path)
        if df.empty:
            print(f"Skipping {label}: no data in 2025 window")
            continue
        ax.plot(df["iso_time"], df["equity"], label=f"{label} Trend")
        any_plotted = True

    if not any_plotted:
        print("No series available for 2025 window; aborting plot.")
        return

    ax.set_title("Intraday Trend Strategy Equity Curves (2025)")
    ax.set_ylabel("Equity Multiple (normalized at 2025-01-01)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_IMAGE, dpi=140)
    print(f"Saved 2025 equity curve comparison to {OUTPUT_IMAGE}")


if __name__ == "__main__":
    main()
