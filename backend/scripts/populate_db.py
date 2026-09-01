"""Populate SQLite database from real loaded pipeline data.

Reads all 647 BYU iceberg tracks and the SAR CFAR candidates,
and seeds the `icebergs` and `iceberg_trajectories` tables.
"""
import sys
import logging
from datetime import datetime

# Adjust path to find app
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import Base, get_engine, SessionLocal
from app.models.iceberg import Iceberg, IcebergTrajectory
from app.core.pipeline import ensure_loaded

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("populate_db")


def main():
    logger.info("Recreating database tables...")
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    
    logger.info("Loading data via pipeline...")
    state = ensure_loaded(include_sar=True)
    tracks = state.get("tracks", [])
    sar_cands = state.get("sar_candidates", [])

    logger.info(f"Populating DB with {len(tracks)} BYU tracks and {len(sar_cands)} SAR candidates...")

    for tr in tracks:
        name = tr["name"]
        points = tr["points"]
        if not points:
            continue
            
        last = points[-1]
        
        # Insert Iceberg
        berg = Iceberg(
            name=name,
            lat=last["lat"],
            lon=last["lon"],
            detected_time=datetime.fromisoformat(last["timestamp"]),
            size_length_nm=last.get("length_km", 0) / 1.852 if last.get("length_km") else None,
            size_width_nm=last.get("width_km", 0) / 1.852 if last.get("width_km") else None,
            source="BYU_MERS",
            confidence=0.9,
            status="CONFIRMED"
        )
        db.add(berg)
        db.flush()  # to get berg.id
        
        # Insert Trajectory
        traj = IcebergTrajectory(
            iceberg_id=berg.id,
            trajectory_type="HISTORICAL",
            points=points,
            confidence_corridor_km=None,
            model_type="NONE"
        )
        db.add(traj)

    for i, c in enumerate(sar_cands):
        berg = Iceberg(
            name=f"SAR_CAND_{i+1:04d}",
            lat=c["lat"],
            lon=c["lon"],
            detected_time=datetime(2026, 8, 22, 21, 45, 29),  # Scene time
            source="S1_CFAR",
            confidence=c["confidence"],
            status="CANDIDATE"
        )
        db.add(berg)

    db.commit()
    db.close()
    
    logger.info("Database population complete.")

if __name__ == "__main__":
    main()
