"""Generate optional local sample telemetry data for exploratory exercises.

Creates reproducible telemetry readings, interval bars, sample service
assignment history, and a SQLite database under the ignored ``sample_data/``
directory. The core workshop and its offline fallbacks do not depend on these
generated files.

Usage:
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "sample_data"


class ReadingRecord(TypedDict):
    asset_id: str
    min_reading: float
    max_reading: float
    last_reading: float
    sample_count: int
    timestamp: str


class IntervalRecord(TypedDict):
    asset_id: str
    open_reading: float
    high_reading: float
    low_reading: float
    close_reading: float
    sample_count: int
    timestamp: str


class AssignmentRecord(TypedDict):
    asset_id: str
    side: str
    hourly_rate: float
    hours: int
    requester_organization_id: str
    provider_organization_id: str
    timestamp: str


def generate_reading_series(
    start_value: float,
    n_points: int,
    mu: float = 0.0001,
    sigma: float = 0.02,
) -> list[float]:
    """Generate a positive synthetic sensor series around its starting value."""
    values = [start_value]
    for _ in range(n_points - 1):
        drift_to_baseline = (start_value - values[-1]) * 0.05
        operating_drift = start_value * mu
        noise = np.random.normal(0, start_value * sigma)
        value = max(0.01, values[-1] + drift_to_baseline + operating_drift + noise)
        values.append(round(value, 2))
    return values


def generate_readings(
    asset_id: str, values: list[float], base_time: datetime
) -> list[ReadingRecord]:
    """Generate telemetry readings from a synthetic value series."""
    readings: list[ReadingRecord] = []
    for i, value in enumerate(values):
        ts = base_time + timedelta(seconds=i * 5)
        readings.append(
            {
                "asset_id": asset_id,
                "min_reading": round(value - 0.01, 2),
                "max_reading": round(value + 0.01, 2),
                "last_reading": value,
                "sample_count": random.randint(100, 10000),
                "timestamp": ts.isoformat(),
            }
        )
    return readings


def generate_intervals(
    readings: list[ReadingRecord], interval_seconds: int = 60
) -> list[IntervalRecord]:
    """Aggregate readings into interval bars."""
    if not readings:
        return []

    bars: list[IntervalRecord] = []
    current_bar: IntervalRecord | None = None
    bar_end: datetime | None = None

    for reading in readings:
        ts = datetime.fromisoformat(reading["timestamp"])
        value = reading["last_reading"]

        if current_bar is None or bar_end is None or ts >= bar_end:
            if current_bar:
                bars.append(current_bar)
            bar_start = ts.replace(second=0, microsecond=0)
            bar_end = bar_start + timedelta(seconds=interval_seconds)
            current_bar = {
                "asset_id": reading["asset_id"],
                "open_reading": value,
                "high_reading": value,
                "low_reading": value,
                "close_reading": value,
                "sample_count": reading["sample_count"],
                "timestamp": bar_start.isoformat(),
            }
        else:
            current_bar["high_reading"] = max(current_bar["high_reading"], value)
            current_bar["low_reading"] = min(current_bar["low_reading"], value)
            current_bar["close_reading"] = value
            current_bar["sample_count"] += reading["sample_count"]

    if current_bar:
        bars.append(current_bar)

    return bars


def generate_assignments(
    asset_id: str, values: list[float], base_time: datetime
) -> list[AssignmentRecord]:
    """Generate sample service-assignment history."""
    assignments: list[AssignmentRecord] = []
    for i in range(0, len(values) - 1, random.randint(5, 20)):
        ts = base_time + timedelta(seconds=i * 5)
        side = random.choice(["REQUEST", "OFFER"])
        hours = random.choice([1, 2, 4, 8, 16, 24])
        assignments.append(
            {
                "asset_id": asset_id,
                "side": side,
                "hourly_rate": values[i],
                "hours": hours,
                "requester_organization_id": f"org_{random.randint(1, 5)}",
                "provider_organization_id": f"org_{random.randint(6, 10)}",
                "timestamp": ts.isoformat(),
            }
        )
    return assignments


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    np.random.seed(42)
    random.seed(42)

    # Synthetic equipment assets with plausible baseline hourly service rates.
    assets = {
        "CNC-01": 85.0,
        "PRESS-04": 120.0,
        "CONV-12": 65.0,
        "ROBOT-07": 110.0,
        "COMP-03": 78.0,
    }

    base_time = datetime(2025, 1, 6, 9, 30, tzinfo=UTC)
    n_points = 2000  # ~2.7 hours of 5-second readings

    all_readings: dict[str, list[ReadingRecord]] = {}
    all_intervals: dict[str, list[IntervalRecord]] = {}
    all_assignments: dict[str, list[AssignmentRecord]] = {}

    for asset_id, start_value in assets.items():
        print(f"Generating data for {asset_id} (start={start_value})...")
        values = generate_reading_series(start_value, n_points)
        readings = generate_readings(asset_id, values, base_time)
        intervals = generate_intervals(readings)
        assignments = generate_assignments(asset_id, values, base_time)

        all_readings[asset_id] = readings
        all_intervals[asset_id] = intervals
        all_assignments[asset_id] = assignments

    # Write JSON files
    for asset_id in assets:
        with open(DATA_DIR / f"{asset_id.lower()}_readings.json", "w", encoding="utf-8") as f:
            json.dump(all_readings[asset_id], f, indent=2)
        with open(DATA_DIR / f"{asset_id.lower()}_intervals.json", "w", encoding="utf-8") as f:
            json.dump(all_intervals[asset_id], f, indent=2)

    # Combined assignments file
    combined_assignments: list[AssignmentRecord] = []
    for assignments in all_assignments.values():
        combined_assignments.extend(assignments)
    combined_assignments.sort(key=lambda a: a["timestamp"])

    with open(DATA_DIR / "assignments.json", "w", encoding="utf-8") as f:
        json.dump(combined_assignments, f, indent=2)

    # Write SQLite database
    db_path = DATA_DIR / "sample_telemetry_data.db"
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            min_reading REAL NOT NULL,
            max_reading REAL NOT NULL,
            last_reading REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intervals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            open_reading REAL NOT NULL,
            high_reading REAL NOT NULL,
            low_reading REAL NOT NULL,
            close_reading REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    for readings in all_readings.values():
        cursor.executemany(
            "INSERT INTO readings "
            "(asset_id, min_reading, max_reading, last_reading, sample_count, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    r["asset_id"],
                    r["min_reading"],
                    r["max_reading"],
                    r["last_reading"],
                    r["sample_count"],
                    r["timestamp"],
                )
                for r in readings
            ],
        )

    for bars in all_intervals.values():
        cursor.executemany(
            "INSERT INTO intervals "
            "(asset_id, open_reading, high_reading, low_reading, close_reading, "
            "sample_count, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    b["asset_id"],
                    b["open_reading"],
                    b["high_reading"],
                    b["low_reading"],
                    b["close_reading"],
                    b["sample_count"],
                    b["timestamp"],
                )
                for b in bars
            ],
        )

    conn.commit()
    conn.close()

    # Summary
    print(f"\n{'=' * 50}")
    print("Sample data generated:")
    print(f"  Readings: {sum(len(r) for r in all_readings.values())} total")
    print(f"  Interval bars: {sum(len(i) for i in all_intervals.values())} total")
    print(f"  Assignments: {len(combined_assignments)} total")
    print(f"  Output: {DATA_DIR}/")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
