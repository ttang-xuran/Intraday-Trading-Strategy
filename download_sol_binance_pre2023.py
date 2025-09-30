import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BINANCE_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "SOLUSDT"
INTERVAL = "5m"
INTERVAL_MS = 5 * 60 * 1000
LIMIT = 1000
OUTPUT_PATH = Path("5-min-SOL.csv")
SLEEP_SECONDS = float(os.getenv("REQUEST_SLEEP", "0.2"))
MAX_BATCHES = int(os.getenv("MAX_BATCHES", "2000"))


def iso_time_from_ms(timestamp_ms: int) -> str:
    seconds = timestamp_ms / 1000.0
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def fetch_candles(end_time: int | None):
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT,
    }
    if end_time is not None:
        params["endTime"] = end_time
    response = requests.get(BINANCE_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Existing SOL dataset not found at {path}")
    df = pd.read_csv(path)
    if "timestamp_ms" not in df.columns:
        raise ValueError("Expected 'timestamp_ms' column in existing dataset")
    df["timestamp_ms"] = df["timestamp_ms"].astype(int)
    return df


def main() -> None:
    existing = load_existing(OUTPUT_PATH)
    earliest_existing = int(existing["timestamp_ms"].min())
    target_end = earliest_existing - INTERVAL_MS
    if target_end <= 0:
        print("Existing file already starts at or before epoch; nothing to download.")
        return

    print(
        f"Existing earliest candle: {iso_time_from_ms(earliest_existing)} ({earliest_existing} ms)."
    )
    print("Fetching additional history from Binance spot API...")

    end_time = target_end
    batch_count = 0
    collected = []
    observed_min = earliest_existing

    while batch_count < MAX_BATCHES and end_time > 0:
        data = fetch_candles(end_time)
        if not data:
            print("Binance returned no data; stopping.")
            break

        batch_count += 1
        first_open_time = int(data[0][0])
        last_open_time = int(data[-1][0])
        print(
            f"Batch {batch_count}: received {len(data)} candles "
            f"[{iso_time_from_ms(first_open_time)} -> {iso_time_from_ms(last_open_time)}]"
        )

        new_items = 0
        for candle in data:
            open_time = int(candle[0])
            if open_time >= earliest_existing:
                continue
            if open_time < observed_min:
                observed_min = open_time
            collected.append(
                {
                    "timestamp_ms": open_time,
                    "iso_time": iso_time_from_ms(open_time),
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "base_volume": candle[5],
                    "quote_volume": candle[7],
                }
            )
            new_items += 1

        if new_items == 0 and first_open_time >= earliest_existing:
            print("No older candles found in this batch; stopping.")
            break

        end_time = first_open_time - INTERVAL_MS
        if len(data) < LIMIT:
            print("Received partial batch; likely reached earliest Binance history.")
            break

        time.sleep(SLEEP_SECONDS)

    if not collected:
        print("No new candles collected; existing dataset is already as old as Binance history.")
        return

    new_df = pd.DataFrame(collected).drop_duplicates(subset="timestamp_ms")
    combined = (
        pd.concat([new_df, existing], ignore_index=True)
        .drop_duplicates(subset="timestamp_ms")
        .sort_values("timestamp_ms")
    )

    combined["timestamp_ms"] = combined["timestamp_ms"].astype(int)

    combined.to_csv(
        OUTPUT_PATH,
        index=False,
        columns=[
            "timestamp_ms",
            "iso_time",
            "open",
            "high",
            "low",
            "close",
            "base_volume",
            "quote_volume",
        ],
    )

    print(
        f"Added {len(new_df)} new candles. New earliest candle: "
        f"{iso_time_from_ms(int(combined['timestamp_ms'].min()))}."
    )


if __name__ == "__main__":
    main()
