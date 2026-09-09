#!/usr/bin/env python3
"""Populate SQLite from BYU tracks + SAR CFAR candidates (real files only)."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.database import SessionLocal, create_tables, init_db
from app.core.config import get_settings
from app.models.iceberg import Iceberg, IcebergTrajectory
from app.data_ingestion.iceberg_loader import IcebergLoader
from app.data_ingestion.sentinel1_loader import Sentinel1Loader
from app.ml.iceberg_detector import IcebergDetector


def main():
    settings = get_settings()
    print(f"Using DB: {settings.DATABASE_URL}")
    print(f"Dataset path: {settings.DATASET_PATH}")
    init_db()
    create_tables()
    db = SessionLocal()
    try:
        db.query(IcebergTrajectory).delete()
        db.query(Iceberg).delete()
        db.commit()

        loader = IcebergLoader(settings.DATASET_PATH)
        tracks = loader.load_all_tracks()
        print(f"BYU merged tracks: {len(tracks)} stats={loader.last_stats}")

        count = 0
        for tr in tracks:
            latest = tr["points"][-1]
            iceberg = Iceberg(
                name=tr["name"],
                lat=latest["lat"],
                lon=latest["lon"],
                detected_time=datetime.fromisoformat(latest["timestamp"]),
                size_length_nm=(latest.get("size_length_km") or 0) / 1.852 or None,
                size_width_nm=(latest.get("size_width_km") or 0) / 1.852 or None,
                source="BYU",
                status="HISTORICAL",
                confidence=0.9,
            )
            db.add(iceberg)
            db.flush()
            db.add(IcebergTrajectory(
                iceberg_id=iceberg.id,
                trajectory_type="HISTORICAL",
                points=tr["points"],
                model_type="BYU_MERGED",
            ))
            count += 1
        db.commit()
        print(f"Loaded {count} BYU icebergs")

        try:
            sar = Sentinel1Loader(settings.DATASET_PATH)
            cands = IcebergDetector().detect(sar, stride=16)
            print(f"SAR CFAR candidates: {len(cands)}")
            for i, c in enumerate(cands[:80]):
                berg = Iceberg(
                    name=f"S1-{i:03d}",
                    lat=c["lat"],
                    lon=c["lon"],
                    detected_time=datetime(2026, 8, 22, 21, 45, 29),
                    source="SAR",
                    status="CANDIDATE",
                    confidence=c["confidence"],
                )
                db.add(berg)
            db.commit()
        except Exception as e:
            print(f"SAR detect skipped: {e}")
            db.rollback()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
    print("Database population complete.")


if __name__ == "__main__":
    main()
