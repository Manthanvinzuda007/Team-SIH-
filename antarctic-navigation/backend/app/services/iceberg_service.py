"""Iceberg service — queries real DB populated from BYU + SAR CFAR."""
from __future__ import annotations

import logging
from typing import Optional

from app.core.database import SessionLocal
from app.models.iceberg import Iceberg, IcebergTrajectory
from app.ml.iceberg_trajectory import IcebergTrajectoryPredictor

logger = logging.getLogger("polaris.iceberg_service")


class IcebergService:
    def get_all_icebergs(self, limit: int = 200, source: Optional[str] = None):
        db = SessionLocal()
        try:
            q = db.query(Iceberg)
            if source:
                q = q.filter(Iceberg.source == source)
            icebergs = q.limit(limit).all()
            return [i.to_dict() for i in icebergs]
        except Exception as e:
            logger.exception("get_all_icebergs error: %s", e)
            return []
        finally:
            db.close()

    def get_iceberg(self, iceberg_id: int):
        db = SessionLocal()
        try:
            return db.query(Iceberg).filter(Iceberg.id == iceberg_id).first()
        finally:
            db.close()

    def get_trajectory(self, iceberg_id: int):
        db = SessionLocal()
        try:
            traj = db.query(IcebergTrajectory).filter(
                IcebergTrajectory.iceberg_id == iceberg_id,
                IcebergTrajectory.trajectory_type == "HISTORICAL",
            ).first()
            if not traj:
                return None
            predictor = IcebergTrajectoryPredictor()
            pts = traj.points or []
            recent = pts[-60:] if len(pts) > 60 else pts
            prediction = predictor.predict(iceberg_id, recent)
            return {
                "iceberg_id": traj.iceberg_id,
                "historical_points": recent,
                "n_historical_total": len(pts),
                "predicted_points": prediction["predicted_points"],
                "confidence_corridor_km": prediction["confidence_corridor_km"],
                "model_type": prediction["model_type"],
                "model_status": "LSTM" if prediction["model_type"] == "LSTM" else "PERSISTENCE_VELOCITY",
                "metrics": prediction.get("metrics"),
                "note": prediction.get("note"),
            }
        except Exception as e:
            logger.exception("get_trajectory error for %d: %s", iceberg_id, e)
            return None
        finally:
            db.close()

    def get_nearby_icebergs(self, lat: float, lon: float, radius_nm: float = 50):
        db = SessionLocal()
        try:
            lat_range = radius_nm / 60.0
            lon_range = radius_nm / (60.0 * max(0.1, abs(lat) / 90.0))
            icebergs = db.query(Iceberg).filter(
                Iceberg.lat >= lat - lat_range,
                Iceberg.lat <= lat + lat_range,
                Iceberg.lon >= lon - lon_range,
                Iceberg.lon <= lon + lon_range,
            ).all()
            return [i.to_dict() for i in icebergs]
        finally:
            db.close()
