from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

DEFAULT_BASE_PATH = Path("intraday_trend_sol_returns.csv")
DEFAULT_OPT_PATH = Path("intraday_trend_sol_opt_returns.csv")
OUTPUT_IMAGE = Path("intraday_trend_sol_equity.png")


def load_equity(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["iso_time"])
    df.sort_values("iso_time", inplace=True)
    df["equity"] = (1.0 + df["return"].astype(float)).cumprod()
    return df[["iso_time", "equity"]]


def main() -> None:
    base = load_equity(DEFAULT_BASE_PATH)
    opt = load_equity(DEFAULT_OPT_PATH)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(base["iso_time"], base["equity"], label="SOL Trend (default)")
    ax.plot(opt["iso_time"], opt["equity"], label="SOL Trend (optimized)")
    ax.set_title("Intraday SOL Trend Strategy Equity Curves")
    ax.set_ylabel("Equity Multiple")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    fig.savefig(OUTPUT_IMAGE, dpi=140)
    print(f"Saved equity curve to {OUTPUT_IMAGE}")


if __name__ == "__main__":
    main()
