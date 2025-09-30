"""
Intraday BTC trend strategy with drawdown control.

Logic
-----
- Source data: 5-minute BTCUSDT closes in `5-min-BTC.csv`.
- Compute multi-day moving averages using 5-minute bars (288 bars ≈ 1 day).
- Go long with leverage when price breaks to a 6-day high while short/medium MAs confirm an uptrend.
- Exit and enforce a 1-day cooldown on a 12% trailing stop, MA breakdown, or large negative bar.
- No shorting; we sit in cash during risk-off periods.
- Apply a 5 bps fee per unit of turnover to approximate execution costs.

Outputs
-------
- `intraday_trend_returns.csv`: strategy daily returns.
- `intraday_trend_exposure.csv`: end-of-day gross exposure.
- `intraday_trend_stats.csv`: performance metrics including buy-and-hold comparison.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_DATA_PATH = Path("5-min-BTC.csv")
OUTPUT_DIR = Path(".")
BARS_PER_DAY = 288

# Strategy parameters (tuned to balance return and drawdown)
DEFAULT_ENTRY_BUFFER = 0.995  # breakout buffer vs. rolling high
DEFAULT_ENTRY_LEVERAGE = 1.30
DEFAULT_TRAILING_STOP = 0.12  # exit if 12% below peak since entry
DEFAULT_COOLDOWN_BARS = BARS_PER_DAY  # stay flat for 1 day after an exit
DEFAULT_PANIC_THRESHOLD = -0.07  # immediate exit if a 5-min bar drops more than 7%
FEE_PER_TURNOVER = 0.0005  # 5 bps per unit position change


def load_series(path: Path) -> pd.Series:
    df = pd.read_csv(path, usecols=["iso_time", "close"], parse_dates=["iso_time"])
    df = df.sort_values("iso_time").set_index("iso_time")
    close = df["close"].astype(float)
    close.name = "close"
    return close


def simulate(
    close: pd.Series,
    entry_buffer: float = DEFAULT_ENTRY_BUFFER,
    entry_leverage: float = DEFAULT_ENTRY_LEVERAGE,
    trailing_stop: float = DEFAULT_TRAILING_STOP,
    cooldown_bars: int = DEFAULT_COOLDOWN_BARS,
    panic_threshold: float = DEFAULT_PANIC_THRESHOLD,
) -> pd.DataFrame:
    returns = close.pct_change().fillna(0.0)

    ma_fast = close.rolling(2 * BARS_PER_DAY, min_periods=1).mean()
    ma_mid = close.rolling(int(3.5 * BARS_PER_DAY), min_periods=1).mean()
    ma_slow = close.rolling(5 * BARS_PER_DAY, min_periods=1).mean()
    rolling_high = close.rolling(6 * BARS_PER_DAY, min_periods=1).max()

    position = np.zeros(len(close), dtype=float)
    state_long = False
    peak_price = 0.0
    cooldown = 0

    for i in range(len(close)):
        price = close.iloc[i]
        if cooldown > 0 and not state_long:
            cooldown -= 1

        if not state_long:
            cond_breakout = (
                cooldown == 0
                and price > ma_mid.iloc[i]
                and ma_fast.iloc[i] > ma_mid.iloc[i]
                and price >= rolling_high.iloc[i] * entry_buffer
            )
            if cond_breakout:
                state_long = True
                peak_price = price
                position[i] = entry_leverage
            else:
                position[i] = 0.0
        else:
            if price > peak_price:
                peak_price = price
            drawdown = price / peak_price - 1.0
            exit_signal = (
                drawdown <= -trailing_stop
                or price < ma_mid.iloc[i]
                or price < ma_slow.iloc[i]
                or returns.iloc[i] < panic_threshold
            )
            if exit_signal:
                state_long = False
                peak_price = 0.0
                cooldown = cooldown_bars
                position[i] = 0.0
            else:
                position[i] = entry_leverage

    position = pd.Series(position, index=close.index, name="position")
    position = position.shift(1).fillna(0.0)

    turnover = position.diff().abs().fillna(0.0)
    fees = turnover * FEE_PER_TURNOVER
    strategy_ret = position * returns - fees

    out = pd.DataFrame({
        "close": close,
        "position": position,
        "return": strategy_ret,
        "turnover": turnover,
    })
    return out


def performance(daily_returns: pd.Series) -> dict[str, float]:
    ann_factor = 365 * (24 * 60 / 5)  # convert 5-min to annual
    cum = (1.0 + daily_returns).cumprod()
    years = len(daily_returns) / ann_factor
    cagr = cum.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 else np.nan
    vol = daily_returns.std() * np.sqrt(ann_factor)
    sharpe = daily_returns.mean() / (daily_returns.std() + 1e-8) * np.sqrt(ann_factor)
    sortino = daily_returns.mean() / (daily_returns[daily_returns < 0].std() + 1e-8) * np.sqrt(ann_factor)
    max_dd = (cum / cum.cummax() - 1.0).min()
    hit_ratio = (daily_returns > 0).mean()
    return {
        "CAGR": cagr,
        "AnnualVol": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "MaxDrawdown": max_dd,
        "HitRatio": hit_ratio,
        "FinalMultiple": cum.iloc[-1],
    }


def run_backtest(
    data_path: Path,
    output_prefix: str = "intraday_trend",
    entry_buffer: float = DEFAULT_ENTRY_BUFFER,
    entry_leverage: float = DEFAULT_ENTRY_LEVERAGE,
    trailing_stop: float = DEFAULT_TRAILING_STOP,
    cooldown_bars: int = DEFAULT_COOLDOWN_BARS,
    panic_threshold: float = DEFAULT_PANIC_THRESHOLD,
) -> dict[str, float]:
    close = load_series(data_path)
    results = simulate(
        close,
        entry_buffer=entry_buffer,
        entry_leverage=entry_leverage,
        trailing_stop=trailing_stop,
        cooldown_bars=cooldown_bars,
        panic_threshold=panic_threshold,
    )

    daily_returns = results["return"].resample("1D").apply(lambda x: (1 + x).prod() - 1)
    daily_exposure = results["position"].resample("1D").last().fillna(0.0)

    stats = performance(results["return"])
    buy_hold = performance(close.pct_change().fillna(0.0))
    stats.update({
        "BuyHoldFinalMultiple": buy_hold["FinalMultiple"],
        "BuyHoldMaxDrawdown": buy_hold["MaxDrawdown"],
    })

    prefix = output_prefix.rstrip(".csv")
    OUTPUT_DIR.joinpath(f"{prefix}_returns.csv").write_text(daily_returns.to_csv(header=True))
    OUTPUT_DIR.joinpath(f"{prefix}_exposure.csv").write_text(daily_exposure.to_csv(header=True))
    OUTPUT_DIR.joinpath(f"{prefix}_stats.csv").write_text(pd.DataFrame(stats, index=[prefix]).to_csv())

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Intraday trend breakout backtest")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH, help="Path to 5-minute OHLC CSV")
    parser.add_argument("--output-prefix", default="intraday_trend", help="Prefix for output CSV files")
    parser.add_argument("--entry-buffer", type=float, default=DEFAULT_ENTRY_BUFFER)
    parser.add_argument("--entry-leverage", type=float, default=DEFAULT_ENTRY_LEVERAGE)
    parser.add_argument("--trailing-stop", type=float, default=DEFAULT_TRAILING_STOP)
    parser.add_argument("--cooldown", type=int, default=DEFAULT_COOLDOWN_BARS)
    parser.add_argument("--panic-threshold", type=float, default=DEFAULT_PANIC_THRESHOLD)
    args = parser.parse_args()

    stats = run_backtest(
        args.data,
        output_prefix=args.output_prefix,
        entry_buffer=args.entry_buffer,
        entry_leverage=args.entry_leverage,
        trailing_stop=args.trailing_stop,
        cooldown_bars=args.cooldown,
        panic_threshold=args.panic_threshold,
    )

    print(f"Backtest complete for {args.data} -> {args.output_prefix}")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
