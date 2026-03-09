"""Generate sample market data for the workshop.

Creates pre-built tick data, OHLC bars, and sample trade history
so attendees have realistic data to work with from the start.

Usage:
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "sample_data"


def generate_price_series(
    start_price: float,
    n_points: int,
    mu: float = 0.0001,
    sigma: float = 0.02,
) -> list[float]:
    """Generate a GBM price series."""
    dt = 1.0 / 252
    prices = [start_price]
    for _ in range(n_points - 1):
        dW = np.random.normal(0, np.sqrt(dt))
        price = prices[-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * dW)
        prices.append(round(price, 2))
    return prices


def generate_ticks(symbol: str, prices: list[float], base_time: datetime) -> list[dict]:
    """Generate tick data from a price series."""
    ticks = []
    for i, price in enumerate(prices):
        ts = base_time + timedelta(seconds=i * 5)
        ticks.append({
            "symbol": symbol,
            "bid": round(price - 0.01, 2),
            "ask": round(price + 0.01, 2),
            "last": price,
            "volume": random.randint(100, 10000),
            "timestamp": ts.isoformat(),
        })
    return ticks


def generate_ohlc(ticks: list[dict], interval_seconds: int = 60) -> list[dict]:
    """Aggregate ticks into OHLC bars."""
    if not ticks:
        return []

    bars = []
    current_bar = None
    bar_end = None

    for tick in ticks:
        ts = datetime.fromisoformat(tick["timestamp"])
        price = tick["last"]

        if current_bar is None or ts >= bar_end:
            if current_bar:
                bars.append(current_bar)
            bar_start = ts.replace(second=0, microsecond=0)
            bar_end = bar_start + timedelta(seconds=interval_seconds)
            current_bar = {
                "symbol": tick["symbol"],
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": tick["volume"],
                "timestamp": bar_start.isoformat(),
            }
        else:
            current_bar["high"] = max(current_bar["high"], price)
            current_bar["low"] = min(current_bar["low"], price)
            current_bar["close"] = price
            current_bar["volume"] += tick["volume"]

    if current_bar:
        bars.append(current_bar)

    return bars


def generate_trades(symbol: str, prices: list[float], base_time: datetime) -> list[dict]:
    """Generate sample trade history."""
    trades = []
    for i in range(0, len(prices) - 1, random.randint(5, 20)):
        ts = base_time + timedelta(seconds=i * 5)
        side = random.choice(["BUY", "SELL"])
        qty = random.choice([10, 25, 50, 100, 200, 500])
        trades.append({
            "symbol": symbol,
            "side": side,
            "price": prices[i],
            "quantity": qty,
            "buyer_id": f"client_{random.randint(1,5)}",
            "seller_id": f"client_{random.randint(6,10)}",
            "timestamp": ts.isoformat(),
        })
    return trades


def main():
    DATA_DIR.mkdir(exist_ok=True)
    np.random.seed(42)
    random.seed(42)

    symbols = {
        "AAPL": 195.0,
        "GOOGL": 175.0,
        "MSFT": 420.0,
        "TSLA": 250.0,
        "AMZN": 185.0,
    }

    base_time = datetime(2025, 1, 6, 9, 30, 0)  # market open
    n_points = 2000  # ~2.7 hours of 5-second ticks

    all_ticks = {}
    all_ohlc = {}
    all_trades = {}

    for symbol, start_price in symbols.items():
        print(f"Generating data for {symbol} (start={start_price})...")
        prices = generate_price_series(start_price, n_points)
        ticks = generate_ticks(symbol, prices, base_time)
        ohlc = generate_ohlc(ticks)
        trades = generate_trades(symbol, prices, base_time)

        all_ticks[symbol] = ticks
        all_ohlc[symbol] = ohlc
        all_trades[symbol] = trades

    # Write JSON files
    for symbol in symbols:
        with open(DATA_DIR / f"{symbol.lower()}_ticks.json", "w") as f:
            json.dump(all_ticks[symbol], f, indent=2)
        with open(DATA_DIR / f"{symbol.lower()}_ohlc.json", "w") as f:
            json.dump(all_ohlc[symbol], f, indent=2)

    # Combined trades file
    combined_trades = []
    for trades in all_trades.values():
        combined_trades.extend(trades)
    combined_trades.sort(key=lambda t: t["timestamp"])

    with open(DATA_DIR / "trades.json", "w") as f:
        json.dump(combined_trades, f, indent=2)

    # Write SQLite database
    db_path = DATA_DIR / "sample_market_data.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            bid REAL NOT NULL,
            ask REAL NOT NULL,
            last REAL NOT NULL,
            volume INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ohlc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    for symbol, ticks in all_ticks.items():
        cursor.executemany(
            "INSERT INTO ticks (symbol, bid, ask, last, volume, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            [(t["symbol"], t["bid"], t["ask"], t["last"], t["volume"], t["timestamp"]) for t in ticks],
        )

    for symbol, bars in all_ohlc.items():
        cursor.executemany(
            "INSERT INTO ohlc (symbol, open, high, low, close, volume, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(b["symbol"], b["open"], b["high"], b["low"], b["close"], b["volume"], b["timestamp"]) for b in bars],
        )

    conn.commit()
    conn.close()

    # Summary
    print(f"\n{'='*50}")
    print("Sample data generated:")
    print(f"  Ticks: {sum(len(t) for t in all_ticks.values())} total")
    print(f"  OHLC bars: {sum(len(o) for o in all_ohlc.values())} total")
    print(f"  Trades: {len(combined_trades)} total")
    print(f"  Output: {DATA_DIR}/")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
