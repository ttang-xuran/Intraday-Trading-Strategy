"""
Long-bias BTC strategy that aims to beat buy-and-hold while tamping max drawdown.

Core ideas
----------
1. Always maintain a small passive long (5%) to keep structural exposure.
2. Size up aggressively when medium/long-term momentum and trend filters agree.
3. De-lever or cut back to minimal exposure when the regime is risk-off (large drawdown, volatility spike, or sudden crash).
4. Volatility-target final exposure (35% annualized cap) and cap leverage at 3.5x.
5. Charge 3 bps per unit turnover to approximate trading costs.

Outputs
-------
- daily_returns.csv: strategy daily % returns
- daily_exposure.csv: end-of-day gross exposure
- long_bias_stats.csv: summary metrics
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path("5-min-BTC.csv")
OUTPUT_DIR = Path(".")

VOL_TARGET = 0.35
TURNOVER_COST = 0.0003


def load_daily_close(path: Path) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["iso_time"], usecols=["iso_time", "close"])
    df = df.sort_values("iso_time")
    df["close"] = df["close"].astype(float)
    daily = df.set_index("iso_time")["close"].resample("1D").last().dropna()
    return daily


def build_exposure(close: pd.Series) -> pd.Series:
    ret = close.pct_change().fillna(0)
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    mom20 = close / close.shift(20) - 1
    mom60 = close / close.shift(60) - 1
    mom120 = close / close.shift(120) - 1
    vol30 = ret.rolling(30).std() * np.sqrt(365)

    rolling_high90 = close.rolling(90).max()
    drawdown90 = close / rolling_high90 - 1

    risk_off = (ret < -0.08) | (drawdown90 < -0.35) | (vol30 > 1.0)

    raw_exp = pd.Series(0.5, index=close.index)
    raw_exp += (close > sma200).astype(float) * 0.7
    raw_exp += (close > sma50).astype(float) * 0.3
    raw_exp += (mom20 > 0).astype(float) * 0.4
    raw_exp += (mom60 > 0.10).astype(float) * 0.3
    raw_exp += (mom120 > 0.20).astype(float) * 0.4
    raw_exp -= (close < sma200).astype(float) * 0.6
    raw_exp -= (mom20 < -0.05).astype(float) * 0.3
    raw_exp -= (mom20 < -0.15).astype(float) * 0.3

    raw_exp = raw_exp.clip(lower=0.05)
    raw_exp = raw_exp.where(~risk_off, raw_exp * 0.2)

    scaler = (VOL_TARGET / (vol30 + 1e-6)).clip(upper=4)
    exposure = (raw_exp * scaler).clip(upper=3.5)
    exposure = exposure.fillna(0.5)
    return exposure


def compute_returns(close: pd.Series) -> pd.DataFrame:
    ret = close.pct_change().fillna(0)
    exposure = build_exposure(close)
    turnover = exposure.diff().abs().fillna(0)
    gross_ret = exposure.shift(1).fillna(exposure.iloc[0]) * ret
    net_ret = gross_ret - TURNOVER_COST * turnover
    out = pd.DataFrame({
        "close": close,
        "return": net_ret,
        "exposure": exposure,
    })
    return out


def performance_stats(daily_returns: pd.Series):
    ann_factor = 365
    cum = (1 + daily_returns).cumprod()
    years = len(daily_returns) / ann_factor
    cagr = cum.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    ann_vol = daily_returns.std() * np.sqrt(ann_factor)
    sharpe = daily_returns.mean() / (daily_returns.std() + 1e-8) * np.sqrt(ann_factor)
    sortino = daily_returns.mean() / (daily_returns[daily_returns < 0].std() + 1e-8) * np.sqrt(ann_factor)
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
    close = load_daily_close(DATA_PATH)
    results = compute_returns(close)
    stats = performance_stats(results["return"])
    buy_hold = performance_stats(close.pct_change().fillna(0))
    stats["BuyHoldFinalMultiple"] = buy_hold["FinalMultiple"]
    stats["BuyHoldMaxDrawdown"] = buy_hold["MaxDrawdown"]

    OUTPUT_DIR.joinpath("daily_returns.csv").write_text(results["return"].to_csv(header=True))
    OUTPUT_DIR.joinpath("daily_exposure.csv").write_text(results["exposure"].to_csv(header=True))
    OUTPUT_DIR.joinpath("long_bias_stats.csv").write_text(pd.DataFrame(stats, index=["LongBias"]).to_csv())


if __name__ == "__main__":
    main()
