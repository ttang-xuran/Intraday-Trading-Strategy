import csv
import importlib.util
import os
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "Test market and limit orders (successful).py"

spec = importlib.util.spec_from_file_location("order_test", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SimpleBitgetOrderTest = module.SimpleBitgetOrderTest
API_KEY = module.API_KEY
SECRET_KEY = module.SECRET_KEY
PASSPHRASE = module.PASSPHRASE

SYMBOL = "SOLUSDT"
GRANULARITY = "5min"
MAX_LIMIT = 200
OUTPUT_PATH = Path("5-min-SOL.csv")
DEFAULT_MAX_BATCHES = int(os.getenv("MAX_BATCHES", "2000"))
REQUEST_SLEEP = float(os.getenv("REQUEST_SLEEP", "0.3"))
RATE_LIMIT_SLEEP = float(os.getenv("RATE_LIMIT_SLEEP", "5"))


def fetch_candles(client, end_time=None, limit=MAX_LIMIT):
    params = {
        "symbol": SYMBOL,
        "granularity": GRANULARITY,
        "limit": limit,
    }
    params["endTime"] = int(time.time() * 1000) if end_time is None else end_time
    return client._make_request(
        "GET",
        "/api/v2/spot/market/history-candles",
        params=params,
    )


def load_existing(path: Path):
    if not path.exists():
        return [], set(), None

    rows = []
    seen = set()
    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            ts = int(record["timestamp_ms"])
            seen.add(ts)
            rows.append(
                {
                    "timestamp_ms": ts,
                    "open": record["open"],
                    "high": record["high"],
                    "low": record["low"],
                    "close": record["close"],
                    "base_volume": record["base_volume"],
                    "quote_volume": record.get("quote_volume", ""),
                }
            )

    earliest = rows[0]["timestamp_ms"] if rows else None
    return rows, seen, earliest


def main():
    client = SimpleBitgetOrderTest(API_KEY, SECRET_KEY, PASSPHRASE)
    all_rows, seen, earliest = load_existing(OUTPUT_PATH)
    end_time = earliest - 1 if earliest is not None else None
    initial_len = len(all_rows)
    max_batches = DEFAULT_MAX_BATCHES
    batch_count = 0

    print(f"Starting download for {SYMBOL} with max_batches={max_batches}")

    while True:
        result = fetch_candles(client, end_time=end_time)
        if not result:
            print("Stopping due to empty API response.")
            break

        code = result.get("code")
        if code == "429":
            print("Rate limit hit; sleeping before retry...")
            time.sleep(RATE_LIMIT_SLEEP)
            continue

        if code != "00000":
            print("Stopping due to API error:", result)
            break

        candles = result.get("data", [])
        if not candles:
            print("No more candles returned; exiting loop.")
            break

        batch_count += 1
        print(f"Fetched batch {batch_count} with {len(candles)} candles (end_time={end_time})")

        for candle in candles:
            ts = int(candle[0])
            if ts in seen:
                continue
            seen.add(ts)
            all_rows.append(
                {
                    "timestamp_ms": ts,
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "base_volume": candle[5],
                    "quote_volume": candle[6] if len(candle) > 6 else "",
                }
            )

        earliest_ts = int(candles[0][0])
        end_time = earliest_ts - 1

        if len(candles) < MAX_LIMIT:
            print("Received final partial batch; exiting loop.")
            break

        if batch_count >= max_batches:
            print("Reached batch cap; saving progress.")
            break

        time.sleep(REQUEST_SLEEP)

    if not all_rows:
        print("No candle data collected; aborting write.")
        return

    all_rows.sort(key=lambda row: row["timestamp_ms"])

    with OUTPUT_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "timestamp_ms",
                "iso_time",
                "open",
                "high",
                "low",
                "close",
                "base_volume",
                "quote_volume",
            ]
        )
        for row in all_rows:
            ts_seconds = (
                row["timestamp_ms"] / 1000
                if row["timestamp_ms"] > 1_000_000_000
                else row["timestamp_ms"]
            )
            iso_time = datetime.fromtimestamp(ts_seconds, tz=timezone.utc).isoformat()
            writer.writerow(
                [
                    row["timestamp_ms"],
                    iso_time,
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["base_volume"],
                    row["quote_volume"],
                ]
            )

    new_rows = len(all_rows) - initial_len
    print(f"Added {new_rows} new rows; wrote {len(all_rows)} rows to {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
