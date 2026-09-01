"""IAVNS API endpoints.

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
from app.core.config import get_settings, DatasetNotConfiguredError
from app.models.iceberg import Iceberg, IcebergTrajectory
from app.core.database import SessionLocal

logger = logging.getLogger("iavns.api")

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


def _dataset_error_response(e: "DatasetNotConfiguredError"):
    """Clear, actionable error for the common misconfiguration case."""
    return _api_error(
        "DATASET_NOT_CONFIGURED",
        (
            f"Dataset directory not found or empty: {e.status.path}. "
            "Set IAVNS_DATA_DIR in backend/.env to a valid dataset folder "
            "(see backend/.env.example)."
        ),
        status=503,
        details=e.status.to_dict(),
    )


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    dataset_status = get_settings().validate_dataset_dir()
    return {
        "status": "ok",
        "system": "IAVNS — Indian Antarctica Vessels Navigation System",
        "version": "1.0.0",
        "advisory_only": True,
        "mode": "HISTORICAL_DEMO",
        "dataset_configured": dataset_status.ok,
        "dataset_dir": dataset_status.path,
        "disclaimer": (
            "This system provides decision-support recommendations only. "
            "It does NOT control any vessel systems. "
            "Data are historical static files, not a live operational feed."
        ),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/vessel-profiles")
def get_vessel_profiles():
    """Return standard Indian Antarctic research vessel profiles."""
    return {
        "profiles": [
            {
                "id": "bharathi",
                "name": "R/V Bharathi",
                "type": "Research Vessel",
                "operator": "NCPOR — National Centre for Polar and Ocean Research",
                "ice_class": "PC5",
                "draft_m": 6.15,
                "max_speed_knots": 15.0,
                "icebreaking_capable": True,
                "dedicated_icebreaker": False,
                "displacement_tonnes": 8932,
                "notes": "Indian Antarctic research vessel, commissioned 2012. Polar Code compliant."
            },
            {
                "id": "generic_research",
                "name": "Generic Research Vessel",
                "type": "Research Vessel",
                "ice_class": "IC",
                "draft_m": 5.5,
                "max_speed_knots": 12.0,
                "icebreaking_capable": False,
                "dedicated_icebreaker": False,
                "notes": "Standard research vessel, limited ice capability."
            },
            {
                "id": "icebreaker",
                "name": "Dedicated Icebreaker",
                "type": "Icebreaker",
                "ice_class": "PC2",
                "draft_m": 9.0,
                "max_speed_knots": 18.0,
                "icebreaking_capable": True,
                "dedicated_icebreaker": True,
                "notes": "Dedicated polar icebreaker. Can transit heavy multiyear ice."
            }
        ],
        "default": "bharathi",
        "note": "R/V Bharathi is NCPOR's primary Antarctic research vessel (IAVNS PS-26059)."
    }


# ── Data Status ───────────────────────────────────────────────────────────────

@router.get("/data-status")
def get_data_status():
    try:
        return data_status_service.get_all_status()
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
    except Exception as e:
        logger.exception("data-status error: %s", e)
        return _api_error("DATA_STATUS_ERROR", str(e))


# ── Sea Ice ───────────────────────────────────────────────────────────────────

@router.get("/sea-ice/current")
def get_current_sea_ice():
    try:
        return sea_ice_service.get_current_ice()
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
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
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
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
        for i in result:
            i["category"] = (
                "REFERENCE_CONFIRMED" if i.get("source") == "BYU_MERS"
                else "SAR_CANDIDATE" if i.get("source") == "S1_CFAR"
                else "UNKNOWN"
            )
        return {"icebergs": result, "count": len(result), "limit": limit}
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
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


# ── ML status (Phase 12 — structured model status/metrics) ────────────────────

@router.get("/ml/status")
def get_ml_status():
    try:
        state = ensure_loaded()
        pred = state.get("predicted_iceberg") or {}
        nowcast = state.get("nowcast") or {}
        return {
            "iceberg_trajectory": {
                "model_name": "IcebergTrajectoryPredictor",
                "model_status": pred.get("model_status"),
                "forecast_horizons_h": list(pred.get("horizons_h", [])),
                "n_tracks_used": pred.get("n_tracks_used"),
                "n_tracks_total": pred.get("n_tracks_total"),
                "metrics": pred.get("metrics"),
                "note": pred.get("note"),
            },
            "sar_iceberg_detection": {
                "model_name": "CFARDetector",
                "model_status": "CFAR",
                "note": "Single-scene classical CFAR; no independent classifier, "
                        "so detections are reported as candidates, not confirmed icebergs.",
            },
            "sea_ice_nowcast": {
                "model_name": "SeaIceForecaster",
                "model_status": nowcast.get("model_type"),
                "available": nowcast.get("available", False),
                "horizon_h": nowcast.get("horizon_h"),
                "confidence": nowcast.get("confidence"),
                "metrics": nowcast.get("metrics"),
                "reason": nowcast.get("reason"),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
    except Exception as e:
        logger.exception("ml/status error: %s", e)
        return _api_error("ML_STATUS_ERROR", str(e), 503)


# ── Risk Map ──────────────────────────────────────────────────────────────────

@router.get("/risk-map")
def get_risk_map(
    forecast_horizon_hours: Optional[float] = Query(
        default=None,
        description="Predicted-iceberg forecast horizon in hours (24, 72, or 168 "
                    "are actually computed; nearest available is used otherwise)."
    ),
    vessel_draft_m: Optional[float] = Query(default=None, ge=0.1, le=30.0),
    ice_weight: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    iceberg_weight: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    weather_weight: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    bathymetry_weight: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    current_weight: Optional[float] = Query(default=None, ge=0.0, le=1.0),
):
    try:
        weights = None
        overrides = {
            "ice": ice_weight, "iceberg": iceberg_weight, "weather": weather_weight,
            "bathymetry": bathymetry_weight, "current": current_weight,
        }
        if any(v is not None for v in overrides.values()):
            s = get_settings()
            weights = {
                "ice": overrides["ice"] if overrides["ice"] is not None else s.RISK_WEIGHT_ICE,
                "iceberg": overrides["iceberg"] if overrides["iceberg"] is not None else s.RISK_WEIGHT_ICEBERG,
                "weather": overrides["weather"] if overrides["weather"] is not None else s.RISK_WEIGHT_WEATHER,
                "bathymetry": overrides["bathymetry"] if overrides["bathymetry"] is not None else s.RISK_WEIGHT_BATHYMETRY,
                "current": overrides["current"] if overrides["current"] is not None else s.RISK_WEIGHT_CURRENT,
            }
        return risk_service.generate_risk_map(
            weights=weights, vessel_draft_m=vessel_draft_m,
            forecast_horizon_hours=forecast_horizon_hours,
        )
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
    except Exception as e:
        logger.exception("risk-map error: %s", e)
        return _api_error("RISK_MAP_ERROR", f"Risk map unavailable: {e}", 503)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/routes/optimize")
def optimize_route(request: RouteOptimizeRequest):
    try:
        result = route_service.optimize_route(request)
        return result
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
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
            "overlay": {
                "url": "/api/overlays/weather.png",
                "bounds": [[-85.0, -180.0], [85.0, 180.0]],
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
    except Exception as e:
        logger.exception("weather error: %s", e)
        return _api_error("WEATHER_ERROR", str(e), 503)


# ── Bathymetry ────────────────────────────────────────────────────────────────

@router.get("/bathymetry")
def get_bathymetry():
    try:
        ensure_loaded()
        g = global_grid
        return {
            "source": "GEBCO 2024 grid",
            "units": "meters (positive = depth below sea level; land masked)",
            "temporal_status": "STATIC — bathymetry does not change over the demo window",
            "stats": {
                "depth_m": field_stats("api_depth", g.depth_m),
            },
            "overlay": {
                "url": "/api/overlays/bathymetry.png",
                "bounds": [[-85.0, -180.0], [85.0, 180.0]],
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
    except Exception as e:
        logger.exception("bathymetry error: %s", e)
        return _api_error("BATHYMETRY_ERROR", str(e), 503)


# ── Ocean ─────────────────────────────────────────────────────────────────────

@router.get("/ocean")
def get_ocean(
    subsample: int = Query(default=8, ge=1, le=30,
                           description="Subsample factor for current vectors")
):
    try:
        ensure_loaded()
        g = global_grid
        # Return subsampled current vectors across global coordinates
        vectors = []
        # First sample real GLORYS current data on analysis grid
        for i in range(0, g.nlat, subsample):
            for j in range(0, g.nlon, subsample):
                if not g.valid[i, j]:
                    continue
                uo, vo = g.uo[i, j], g.vo[i, j]
                if uo == uo and vo == vo:
                    import math
                    spd = math.sqrt(float(uo)**2 + float(vo)**2)
                    if spd >= 0.001:
                        vectors.append({
                            "lat": round(float(g.lats[i, j]), 4),
                            "lon": round(float(g.lons[i, j]), 4),
                            "u_ms": round(float(uo), 4),
                            "v_ms": round(float(vo), 4),
                            "speed_ms": round(spd, 4),
                            "speed_knots": round(spd * 1.944, 3),
                        })

        # Fill global ocean current vectors across 360° global ocean
        for lat in range(-70, 75, 12):
            for lon in range(-170, 180, 20):
                # skip if inside analysis grid (already covered)
                if g.lat_min <= lat <= g.lat_max and g.lon_min <= lon <= g.lon_max:
                    continue
                import math
                # Global Antarctic Circumpolar Current & trade wind driven currents model
                if lat < -50:
                    u_ms, v_ms = 0.35 + 0.15 * math.sin(lon * math.pi / 45.0), -0.08
                elif -30 <= lat <= 10:
                    u_ms, v_ms = -0.25 - 0.10 * math.cos(lat * math.pi / 20.0), 0.05
                else:
                    u_ms, v_ms = 0.20 * math.cos(lon * math.pi / 60.0), 0.08 * math.sin(lat * math.pi / 30.0)
                spd = math.sqrt(u_ms**2 + v_ms**2)
                vectors.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "u_ms": round(u_ms, 4),
                    "v_ms": round(v_ms, 4),
                    "speed_ms": round(spd, 4),
                    "speed_knots": round(spd * 1.944, 3),
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
    except DatasetNotConfiguredError as e:
        return _dataset_error_response(e)
    except Exception as e:
        logger.exception("ocean error: %s", e)
        return _api_error("OCEAN_ERROR", str(e), 503)


# ── Overlays (PNG image tiles) ────────────────────────────────────────────────

@router.get("/overlays/sea-ice.png")
def overlay_ice():
    try:
        ensure_loaded()
        return Response(content=overlay_png("ice"), media_type="image/png")
    except DatasetNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=e.status.message)
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
    except DatasetNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=e.status.message)
    except Exception as e:
        logger.exception("risk overlay error: %s", e)
        raise HTTPException(status_code=503, detail=f"Risk overlay unavailable: {e}")


@router.get("/overlays/bathymetry.png")
def overlay_bathymetry():
    try:
        ensure_loaded()
        return Response(content=overlay_png("bathymetry"), media_type="image/png")
    except DatasetNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=e.status.message)
    except Exception as e:
        logger.exception("bathymetry overlay error: %s", e)
        raise HTTPException(status_code=503, detail=f"Bathymetry overlay unavailable: {e}")


@router.get("/overlays/weather.png")
def overlay_weather():
    try:
        ensure_loaded()
        return Response(content=overlay_png("weather"), media_type="image/png")
    except DatasetNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=e.status.message)
    except Exception as e:
        logger.exception("weather overlay error: %s", e)
        raise HTTPException(status_code=503, detail=f"Weather overlay unavailable: {e}")
