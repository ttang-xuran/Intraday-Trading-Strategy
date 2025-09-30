import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path("5-min-BTC.csv")
OUTPUT_DIR = Path(".")

FILTER_MOMENTUM = 10  # days
VOL_TARGET = 0.20
COST_PER_TURNOVER = 0.0005
ATR_LOOKBACK = 6
ATR_MULTIPLIER = 1.0
RET_SCALER_WINDOW = 24  # 24 * 4h = 4 days


def load_prices():
    df = pd.read_csv(DATA_PATH, parse_dates=["iso_time"], usecols=["iso_time", "close"])
    df = df.sort_values("iso_time").set_index("iso_time")
    df["close"] = df["close"].astype(float)
    return df


def build_breakout_returns(prices: pd.DataFrame, apply_momentum_filter: bool):
    h4 = prices["close"].resample("4h").ohlc().dropna()
    h4["ret"] = np.log(h4["close"]).diff().fillna(0)

    rolling_tr = pd.concat([
        h4["high"] - h4["low"],
        (h4["high"] - h4["close"].shift(1)).abs(),
        (h4["low"] - h4["close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = rolling_tr.rolling(ATR_LOOKBACK).mean()
    prev_high = h4["high"].rolling(ATR_LOOKBACK).max().shift(1)
    prev_low = h4["low"].rolling(ATR_LOOKBACK).min().shift(1)

    upper = prev_high + ATR_MULTIPLIER * atr
    lower = prev_low - ATR_MULTIPLIER * atr

    signal = pd.Series(0, index=h4.index, dtype=float)
    signal.loc[h4["high"] > upper] = 1.0
    signal.loc[h4["low"] < lower] = -1.0
    signal = signal.replace(to_replace=0, method="ffill").fillna(0.0)
    position = signal.shift(1).fillna(0.0)

    if apply_momentum_filter:
        daily_close = prices["close"].resample("1D").last().dropna()
        momentum = daily_close / daily_close.shift(FILTER_MOMENTUM) - 1
        momentum = momentum.reindex(h4.index, method="ffill").fillna(0.0)
        position = position.where(momentum > 0, 0.0)

    realized_vol = h4["ret"].rolling(RET_SCALER_WINDOW).std() * np.sqrt(RET_SCALER_WINDOW * 365)
    scaler = (VOL_TARGET / (realized_vol + 1e-6)).clip(upper=3)
    position = position * scaler
    turnover = position.diff().abs().fillna(0.0)

    strategy_ret = position * h4["ret"] - turnover * COST_PER_TURNOVER
    daily_ret = strategy_ret.groupby(strategy_ret.index.date).sum()
    daily_ret.index = pd.to_datetime(daily_ret.index).tz_localize("UTC")
    return daily_ret


def performance_stats(daily_returns: pd.Series):
    daily_returns = daily_returns.copy()
    ann_factor = 365
    cum = (1 + daily_returns).cumprod()
    years = len(daily_returns) / ann_factor
    cagr = cum.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    ann_vol = daily_returns.std() * np.sqrt(ann_factor)
    sharpe = daily_returns.mean() / (daily_returns.std() + 1e-8) * np.sqrt(ann_factor)
    neg_std = daily_returns[daily_returns < 0].std()
    sortino = daily_returns.mean() / (neg_std + 1e-8) * np.sqrt(ann_factor)
    max_dd = (cum / cum.cummax() - 1).min()
    hit_ratio = (daily_returns > 0).mean()
    return {
        "CAGR": cagr,
        "AnnualVol": ann_vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "MaxDrawdown": max_dd,
        "HitRatio": hit_ratio,
        "FinalMultiple": cum.iloc[-1]
    }


def main():
    prices = load_prices()

    base_returns = build_breakout_returns(prices, apply_momentum_filter=False)
    filt_returns = build_breakout_returns(prices, apply_momentum_filter=True)

    base_stats = performance_stats(base_returns)
    filt_stats = performance_stats(filt_returns)

    stats_df = pd.DataFrame({
        "ATR6x1 breakout": base_stats,
        "ATR6x1 + 10d momentum filter": filt_stats
    })

    OUTPUT_DIR.joinpath("breakout_daily_returns.csv").write_text(
        base_returns.to_csv(header=["ret"])
    )
    OUTPUT_DIR.joinpath("breakout_daily_returns_filtered.csv").write_text(
        filt_returns.to_csv(header=["ret"])
    )
    OUTPUT_DIR.joinpath("breakout_monthly_returns.csv").write_text(
        base_returns.resample("M").apply(lambda x: (1 + x).prod() - 1).to_csv(header=["return"])
    )
    OUTPUT_DIR.joinpath("breakout_rolling_sharpe.csv").write_text(
        (base_returns.rolling(90).mean() / (base_returns.rolling(90).std() + 1e-8) * np.sqrt(365)).to_csv(header=["sharpe"])
    )
    OUTPUT_DIR.joinpath("strategy_stats.csv").write_text(stats_df.to_csv(index=True))


if __name__ == "__main__":
    main()
