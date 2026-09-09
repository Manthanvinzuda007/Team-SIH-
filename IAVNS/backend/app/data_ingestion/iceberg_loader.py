"""BYU MERS Antarctic iceberg tracking database loader.

Real data: 647 CSV files, one per named iceberg. 8 possible sensor prefixes:
  ascat, ers, nic, nscat, oscat, qscat, sass, seawinds
Format: date (YYYYDDD Julian), {sensor}_1 (lat), {sensor}_2 (lon), {sensor}_3 (flag),
  size_1 (length km), size_2 (width km).

This loader detects ALL sensor prefixes per file, merges into one deduplicated
time-sorted track per iceberg, preferring nic positions when multiple sensors
report the same day (NIC positions are verified chart positions).
"""
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.data_ingestion.base_loader import BaseLoader

logger = logging.getLogger("polaris.iceberg")

# Sensor quality ranking (higher = preferred when multiple report same day)
SENSOR_PRIORITY = {
    "nic": 10,   # NIC chart positions — highest quality
    "ascat": 7,
    "qscat": 6,
    "oscat": 5,
    "seawinds": 4,
    "nscat": 3,
    "ers": 2,
    "sass": 1,
}


def _julian_to_datetime(yyyyddd: int) -> Optional[datetime]:
    """Convert YYYYDDD Julian date to datetime."""
    s = str(int(yyyyddd))
    if len(s) != 7:
        return None
    try:
        year = int(s[:4])
        doy = int(s[4:])
        return datetime(year, 1, 1) + timedelta(days=doy - 1)
    except (ValueError, OverflowError):
        return None


def _detect_sensor_prefixes(columns: List[str]) -> List[str]:
    """Find all sensor prefixes in a CSV's column names."""
    prefixes = []
    for col in columns:
        if col.endswith("_1") and col != "size_1":
            prefixes.append(col[:-2])
    return prefixes


class IcebergLoader(BaseLoader):
    """Load all BYU MERS iceberg CSV tracks."""

    def __init__(self, dataset_path: str):
        super().__init__(dataset_path)
        self.dataset_name = "BYU MERS Iceberg Tracks"
        self.dataset_type = "BYU"
        # Exclude editor swap files
        all_csvs = self.search_files(["*.csv"])
        self.files = [f for f in all_csvs if not os.path.basename(f).startswith("#")]

    def validate_file(self, filepath: str) -> bool:
        try:
            df = pd.read_csv(filepath, nrows=1)
            return "date" in df.columns
        except Exception:
            return False

    def parse_metadata(self, filepath: str) -> Dict[str, Any]:
        return {}

    def load(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Load a single iceberg CSV, merging all sensor readings into one track."""
        if not os.path.exists(filepath):
            return None

        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            logger.warning("Cannot read %s: %s", filepath, e)
            return None

        if "date" not in df.columns:
            return None

        prefixes = _detect_sensor_prefixes(df.columns.tolist())
        if not prefixes:
            return None

        # Build position records from all sensors
        records = []
        for _, row in df.iterrows():
            julian = row["date"]
            dt = _julian_to_datetime(julian)
            if dt is None:
                continue

            # Collect all sensor readings for this date
            best_lat = None
            best_lon = None
            best_prio = -1

            for prefix in prefixes:
                lat_col = f"{prefix}_1"
                lon_col = f"{prefix}_2"
                if lat_col not in row.index or lon_col not in row.index:
                    continue

                lat = row[lat_col]
                lon = row[lon_col]

                # Validate: must be finite, non-zero, and in Antarctic waters
                if pd.isna(lat) or pd.isna(lon):
                    continue
                if lat == 0 and lon == 0:
                    continue
                if lat > -50:  # Not Antarctic
                    continue

                prio = SENSOR_PRIORITY.get(prefix, 0)
                if prio > best_prio:
                    best_lat = float(lat)
                    best_lon = float(lon)
                    best_prio = prio

            if best_lat is not None:
                rec = {
                    "timestamp": dt.isoformat(),
                    "lat": best_lat,
                    "lon": best_lon,
                }
                # Add size if available
                if "size_1" in row.index and "size_2" in row.index:
                    s1 = row["size_1"]
                    s2 = row["size_2"]
                    if pd.notna(s1) and s1 > 0:
                        rec["length_km"] = float(s1)
                    if pd.notna(s2) and s2 > 0:
                        rec["width_km"] = float(s2)

                records.append(rec)

        # Sort by time and deduplicate by date
        records.sort(key=lambda r: r["timestamp"])
        seen_dates = set()
        deduped = []
        for r in records:
            d = r["timestamp"][:10]
            if d not in seen_dates:
                seen_dates.add(d)
                deduped.append(r)

        name = os.path.basename(filepath).replace(".csv", "")
        return {
            "name": name,
            "points": deduped,
            "n_points": len(deduped),
            "source": "BYU MERS",
        }

    def load_all_tracks(self) -> List[Dict[str, Any]]:
        """Load all iceberg tracks. Returns list of track dicts."""
        tracks = []
        for fp in self.files:
            track = self.load(fp)
            if track and track["n_points"] >= 2:
                tracks.append(track)
        logger.info("Loaded %d iceberg tracks (with ≥2 points) from %d files",
                     len(tracks), len(self.files))
        return tracks

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "name": self.dataset_name,
            "type": self.dataset_type,
            "status": "READY" if self.files else "UNAVAILABLE",
            "files_found": len(self.files),
            "sensor_prefixes": sorted(SENSOR_PRIORITY.keys()),
            "note": "Multi-decade iceberg tracks. Multi-sensor merge with NIC preference.",
        }
