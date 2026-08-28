"""POLARIS API endpoints.

All endpoints return structured errors; no Python tracebacks are exposed.
Units are documented in each response payload.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from app.schemas.route import RouteOptimizeRequest
from app.services.sea_ice_service import SeaIceService, SUPPORTED_HORIZONS
from app.services.iceberg_service import IcebergService
from app.services.route_service import RouteService
from app.services.risk_service import RiskService
from app.services.data_status_service import DataStatusService
from app.core.pipeline import ensure_loaded, overlay_png
from app.core.grid import global_grid
from app.core.geo import field_stats
from app.core.database import create_tables
from app.models.iceberg import Iceberg, IcebergTrajectory
from app.core.database import SessionLocal

logger = logging.getLogger("polaris.api")

router = APIRouter()

sea_ice_service = SeaIceService()
iceberg_service = IcebergService()
route_service = RouteService()
risk_service = RiskService()
data_status_service = DataStatusService()


def _api_error(code: str, message: str, status: int = 500, details: dict = None):
    return JSONResponse(
        status_code=status,
        content={"error": True, "code": code, "message": message, "details": details or {}},
    )


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "system": "POLARIS Antarctic Navigation Decision Support System",
        "version": "1.0.0",
        "advisory_only": True,
        "mode": "HISTORICAL_DEMO",
        "disclaimer": (
            "This system provides decision-support recommendations only. "
            "It does NOT control any vessel systems. "
            "Data are historical static files, not a live operational feed."
        ),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ── Data Status ───────────────────────────────────────────────────────────────

@router.get("/data-status")
def get_data_status():
    try:
        return data_status_service.get_all_status()
    except Exception as e:
        logger.exception("data-status error: %s", e)
        return _api_error("DATA_STATUS_ERROR", str(e))


# ── Sea Ice ───────────────────────────────────────────────────────────────────

@router.get("/sea-ice/current")
def get_current_sea_ice():
    try:
        return sea_ice_service.get_current_ice()
    except Exception as e:
        logger.exception("sea-ice/current error: %s", e)
        return _api_error("SEA_ICE_ERROR", f"Sea ice data unavailable: {e}", 503)


@router.get("/sea-ice/forecast")
def get_sea_ice_forecast(
    hours: str = Query(
        default="6,12,18,24,30,36,42,48",
        description="Comma-separated forecast horizons in hours (1–48). "
                    "Example: hours=6,12,24"
    )
):
    try:
        parsed = []
        for tok in hours.split(","):
            tok = tok.strip()
            if tok.isdigit():
                h = int(tok)
                if 1 <= h <= 48:
                    parsed.append(h)
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Horizon {h} out of range 1–48"
                    )
            elif tok:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid horizon token: '{tok}'"
                )
        if not parsed:
            parsed = SUPPORTED_HORIZONS
        return sea_ice_service.get_forecast(parsed)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("sea-ice/forecast error: %s", e)
        return _api_error("FORECAST_ERROR", f"Forecast unavailable: {e}", 503)


# ── Icebergs ──────────────────────────────────────────────────────────────────

@router.get("/icebergs")
def get_icebergs(
    limit: int = Query(default=200, ge=1, le=2000),
    source: Optional[str] = Query(default=None, description="Filter by source: BYU_MERS, S1_CFAR"),
):
    try:
        result = iceberg_service.get_all_icebergs(limit=limit, source=source)
        return {"icebergs": result, "count": len(result), "limit": limit}
    except Exception as e:
        logger.exception("icebergs error: %s", e)
        return _api_error("ICEBERG_ERROR", str(e))


@router.get("/icebergs/{iceberg_id}/trajectory")
def get_iceberg_trajectory(iceberg_id: int):
    try:
        traj = iceberg_service.get_trajectory(iceberg_id)
        if not traj:
            raise HTTPException(status_code=404, detail=f"Trajectory not found for iceberg {iceberg_id}")
        return traj
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("iceberg trajectory error: %s", e)
        return _api_error("TRAJECTORY_ERROR", str(e))


# ── Risk Map ──────────────────────────────────────────────────────────────────

@router.get("/risk-map")
def get_risk_map():
    try:
        return risk_service.generate_risk_map()
    except Exception as e:
        logger.exception("risk-map error: %s", e)
        return _api_error("RISK_MAP_ERROR", f"Risk map unavailable: {e}", 503)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/routes/optimize")
def optimize_route(request: RouteOptimizeRequest):
    try:
        result = route_service.optimize_route(request)
        return result
    except Exception as e:
        logger.exception("routes/optimize error: %s", e)
        return _api_error("ROUTE_ERROR", f"Route optimization failed: {e}", 503)


@router.get("/routes/{route_id}")
def get_route(route_id: int):
    db = SessionLocal()
    try:
        from app.models.route import SavedRoute
        route = db.query(SavedRoute).filter(SavedRoute.id == route_id).first()
        if not route:
            raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
        return route.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get route %d error: %s", route_id, e)
        return _api_error("ROUTE_FETCH_ERROR", str(e))
    finally:
        db.close()


@router.post("/routes/save")
def save_route(body: dict):
    """Persist a computed route for later retrieval."""
    db = SessionLocal()
    try:
        from app.models.route import SavedRoute
        sr = SavedRoute(
            mode=body.get("mode", "UNKNOWN"),
            origin_lat=body.get("origin_lat"),
            origin_lon=body.get("origin_lon"),
            dest_lat=body.get("dest_lat"),
            dest_lon=body.get("dest_lon"),
            distance_nm=body.get("distance_nm"),
            eta_hours=body.get("estimated_time_hours"),
            risk_score=body.get("risk_score"),
            path_points=body.get("path_points", []),
            vessel_config=body.get("vessel_config"),
            data_snapshot=body.get("data_valid_time", "2026-08-08"),
        )
        db.add(sr)
        db.commit()
        db.refresh(sr)
        return {"saved": True, "route_id": sr.id}
    except Exception as e:
        db.rollback()
        logger.exception("save route error: %s", e)
        return _api_error("ROUTE_SAVE_ERROR", str(e))
    finally:
        db.close()


# ── Weather ───────────────────────────────────────────────────────────────────

@router.get("/weather")
def get_weather():
    try:
        ensure_loaded()
        g = global_grid
        return {
            "source": "ERA5 instant+accum merged (u10, v10, t2m, msl, tp)",
            "valid_time": "2026-08-08T23:00:00Z",
            "coverage": "2026-08-01..08, 16 timesteps, using last snapshot on analysis grid",
            "temporal_status": "HISTORICAL — static ERA5 reanalysis, not NWP forecast",
            "stats": {
                "wind_speed_ms": field_stats("api_wind", g.wind_speed),
                "t2m_K": field_stats("api_t2m", g.t2m),
                "msl_Pa": field_stats("api_msl", g.msl),
                "u10_ms": field_stats("api_u10", g.u10),
                "v10_ms": field_stats("api_v10", g.v10),
            },
            "note": "No wave-height file in dataset; wind speed is weather-risk proxy.",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.exception("weather error: %s", e)
        return _api_error("WEATHER_ERROR", str(e), 503)


# ── Ocean ─────────────────────────────────────────────────────────────────────

@router.get("/ocean")
def get_ocean(
    subsample: int = Query(default=8, ge=1, le=30,
                           description="Subsample factor for current vectors")
):
    try:
        ensure_loaded()
        g = global_grid
        # Return subsampled current vectors for frontend visualization
        vectors = []
        for i in range(0, g.nlat, subsample):
            for j in range(0, g.nlon, subsample):
                if not g.valid[i, j]:
                    continue
                uo = g.uo[i, j]
                vo = g.vo[i, j]
                if not (uo == uo and vo == vo):  # nan check
                    continue
                import math
                speed_ms = math.sqrt(float(uo)**2 + float(vo)**2)
                if speed_ms < 0.001:
                    continue
                vectors.append({
                    "lat": round(float(g.lats[i, j]), 4),
                    "lon": round(float(g.lons[i, j]), 4),
                    "u_ms": round(float(uo), 4),
                    "v_ms": round(float(vo), 4),
                    "speed_ms": round(speed_ms, 4),
                    "speed_knots": round(speed_ms * 1.944, 3),
                })
        return {
            "source": "CMEMS GLORYS12 daily-mean reanalysis",
            "valid_time": "2026-06-01..08 mean",
            "temporal_status": "HISTORICAL — NOT contemporaneous with Aug 2026 sea-ice data",
            "temporal_warning": (
                "GLORYS data are June 2026; AMSR2/ERA5 are August 2026. "
                "Currents cannot be assumed to match ice conditions."
            ),
            "depth": "surface (~0.494 m)",
            "n_vectors": len(vectors),
            "vectors": vectors,
            "stats": {
                "uo_ms": field_stats("api_uo", g.uo),
                "vo_ms": field_stats("api_vo", g.vo),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.exception("ocean error: %s", e)
        return _api_error("OCEAN_ERROR", str(e), 503)


# ── Overlays (PNG image tiles) ────────────────────────────────────────────────

@router.get("/overlays/sea-ice.png")
def overlay_ice():
    try:
        ensure_loaded()
        return Response(content=overlay_png("ice"), media_type="image/png")
    except Exception as e:
        logger.exception("ice overlay error: %s", e)
        raise HTTPException(status_code=503, detail=f"Ice overlay unavailable: {e}")


@router.get("/overlays/risk.png")
def overlay_risk():
    try:
        ensure_loaded()
        g = global_grid
        import numpy as np
        if g.risk_grid is None or not np.isfinite(g.risk_grid).any():
            risk_service.generate_risk_map()
        return Response(content=overlay_png("risk"), media_type="image/png")
    except Exception as e:
        logger.exception("risk overlay error: %s", e)
        raise HTTPException(status_code=503, detail=f"Risk overlay unavailable: {e}")
