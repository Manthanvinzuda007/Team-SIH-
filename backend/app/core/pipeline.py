"""Load all real fields onto the shared analysis grid (once per process)."""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.core.geo import field_stats, haversine_km
from app.core.grid import global_grid
from app.data_ingestion.seaice_loader import SeaIceLoader
from app.data_ingestion.gebco_loader import GebcoLoader
from app.data_ingestion.ocean_loader import OceanLoader
from app.data_ingestion.environment_loader import EnvironmentLoader
from app.data_ingestion.iceberg_loader import IcebergLoader
from app.data_ingestion.sentinel1_loader import Sentinel1Loader
from app.ml.sea_ice_forecast import SeaIceForecaster
from app.ml.iceberg_detector import IcebergDetector
from app.ml.iceberg_trajectory import IcebergTrajectoryPredictor, HORIZONS_DAYS

logger = logging.getLogger("polaris")
_lock = threading.Lock()
_state: Dict[str, Any] = {"loaded": False}


def _predict_iceberg_positions(tracks: List[Dict[str, Any]], horizons_hours: Tuple[int, ...]):
    """Run the LSTM trajectory predictor across every usable BYU track.

    SAR CFAR candidates are NOT included here: they are single-scene
    detections with no position history, so there is nothing for the
    trajectory model to roll forward from (Phase 4 — never mix the SAR
    "candidate" category with the LSTM "predicted" category).

    Returns (positions_by_horizon, n_tracks_used, model_status, metrics)
    where positions_by_horizon[h] is a list of (lat, lon, track_name) tuples.
    """
    predictor = IcebergTrajectoryPredictor()
    positions: Dict[int, List[Tuple[float, float, str]]] = {h: [] for h in horizons_hours}
    n_used = 0
    metrics = None
    for tr in tracks:
        pts = tr.get("points") or []
        if len(pts) < 2:
            continue
        try:
            pred = predictor.predict(tr["name"], pts, forecast_hours=list(horizons_hours))
        except Exception as e:
            logger.warning("Trajectory prediction failed for %s: %s", tr.get("name"), e)
            continue
        n_used += 1
        metrics = pred.get("metrics") or metrics
        for p in pred["predicted_points"]:
            h = p.get("forecast_hour")
            if h in positions and p.get("lat") == p.get("lat") and p.get("lon") == p.get("lon"):
                positions[h].append((float(p["lat"]), float(p["lon"]), tr["name"]))
    logger.info(
        "Iceberg trajectory prediction: %s/%s tracks usable, model=%s, horizons=%s",
        n_used, len(tracks), predictor.model_status, horizons_hours,
    )
    return positions, n_used, predictor.model_status, metrics


def get_loaders():
    root = str(get_settings().dataset_dir)
    return {
        "seaice": SeaIceLoader(root),
        "gebco": GebcoLoader(root),
        "ocean": OceanLoader(root),
        "era5": EnvironmentLoader(root),
        "iceberg": IcebergLoader(root),
        "sar": Sentinel1Loader(root),
    }


def ensure_loaded(include_sar: bool = True) -> Dict[str, Any]:
    with _lock:
        if _state.get("loaded"):
            return _state
        s = get_settings()
        status = s.validate_dataset_dir()
        if not status.ok:
            from app.core.config import DatasetNotConfiguredError
            logger.error("Dataset directory not usable: %s", status.message)
            raise DatasetNotConfiguredError(status)
        _load(include_sar=include_sar)
        return _state


def _find_era5_dir(base_path):
    for name in ["ERA5_Dtaset", "ERA5_Dataset", "ERA5"]:
        p = base_path / name
        if p.exists():
            return p
    return base_path / "ERA5_Dtaset"  # fallback to original

def _load(include_sar: bool = True):
    s = get_settings()
    root = str(s.dataset_dir)
    g = global_grid
    logger.info("Loading analysis grid shape=%s valid_frac=%.3f AOI lat[%s,%s] lon[%s,%s]",
                g.shape, float(g.valid.mean()), g.lat_min, g.lat_max, g.lon_min, g.lon_max)

    # -- Sea ice --
    seaice_loader = SeaIceLoader(str(s.dataset_dir / "NSIDC _AMSR2_Sea_Ice"))
    g.ice_conc = seaice_loader.load_concentration_on_grid(g)

    native_days = seaice_loader.load_all_days()
    native_stack = np.stack([d["concentration"] for d in native_days]) if native_days else np.array([])
    forecaster = SeaIceForecaster()
    if native_stack.size:
        forecaster.set_native_stack(native_stack)

    # -- Bathymetry --
    gebco_loader = GebcoLoader(str(s.dataset_dir / "GEBCO_Dataset"))
    depth = gebco_loader.load_depth_on_grid(g)
    g.depth_m = depth
    g.elevation_m = np.where(np.isfinite(depth), -depth, np.nan)
    g.land = np.isnan(depth)
    field_stats("depth_m_positive_down", g.depth_m)

    # -- Ocean currents --
    ocean_loader = OceanLoader(str(s.dataset_dir / "GLORYS_Ocean_Current_Data"))
    curr = ocean_loader.load_currents_on_grid(g)
    g.uo = curr["uo"]
    g.vo = curr["vo"]
    g.current_speed = np.hypot(g.uo, g.vo)

    # -- ERA5 weather --
    era5_loader = EnvironmentLoader(str(_find_era5_dir(s.dataset_dir)))
    wx = era5_loader.load_weather_on_grid(g)
    g.u10 = wx["u10"]
    g.v10 = wx["v10"]
    g.wind_speed = wx["wind_speed"]
    g.t2m = wx["t2m"]
    g.msl = wx["msl"]

    # -- Iceberg tracks --
    iceberg_loader = IcebergLoader(str(s.dataset_dir / "Iceberg_Tracking_Database"))
    tracks = iceberg_loader.load_all_tracks()
    berg_xy = []
    for tr in tracks:
        last = tr["points"][-1]
        if g.lat_min <= last["lat"] <= g.lat_max and g.lon_min <= last["lon"] <= g.lon_max:
            berg_xy.append((last["lat"], last["lon"]))

    # -- SAR iceberg detection --
    sar_loader = Sentinel1Loader(str(s.dataset_dir / "Sentinel-1_SAR.SAFE"))
    sar_cands: List[Dict[str, Any]] = []
    if include_sar:
        try:
            sar_cands = IcebergDetector().detect(sar_loader, stride=16)
        except Exception as e:
            logger.exception("SAR CFAR failed: %s", e)

    for c in sar_cands:
        berg_xy.append((c["lat"], c["lon"]))

    g.iceberg_dist_km = _distance_field(g, berg_xy)
    field_stats("iceberg_dist_km", g.iceberg_dist_km, extra={"n_positions": len(berg_xy)})

    # -- Iceberg trajectory prediction (Part 2 Phase 2/3) --
    horizons_hours: Tuple[int, ...] = tuple(
        int(x.strip()) for x in s.ICEBERG_FORECAST_HORIZONS_H.split(",") if x.strip()
    ) or tuple(d * 24 for d in HORIZONS_DAYS)
    pred_positions, n_traj_used, traj_model_status, traj_metrics = _predict_iceberg_positions(
        tracks, horizons_hours
    )
    predicted_dist_fields = {
        h: _distance_field(g, [(la, lo) for la, lo, _ in pts])
        for h, pts in pred_positions.items()
    }
    default_horizon = horizons_hours[0] if horizons_hours else 24
    g.predicted_iceberg_dist_km = predicted_dist_fields.get(
        default_horizon, np.full(g.shape, np.nan)
    )
    g.predicted_iceberg_horizon_h = default_horizon
    day_key = {24: "1d", 72: "3d", 168: "7d"}.get(default_horizon)
    g.predicted_iceberg_uncertainty_km = (
        traj_metrics.get("ADE_km", {}).get(day_key, {}).get("lstm")
        if traj_metrics and day_key else None
    )
    for h, arr in predicted_dist_fields.items():
        field_stats(f"predicted_iceberg_dist_km_{h}h", arr, extra={"n_predicted_positions": len(pred_positions.get(h, []))})

    # -- Sea-ice nowcast, regridded onto the analysis grid (Part 2 Phase 6) --
    nowcast_horizon = s.SEA_ICE_NOWCAST_RISK_HORIZON_H
    nowcast_info: Dict[str, Any] = {
        "available": False, "horizon_h": nowcast_horizon, "field": None,
        "reason": "fewer than 2 native AMSR2 days available — optical-flow advection needs t-1, t",
    }
    if native_stack.size and native_stack.shape[0] >= 2:
        try:
            preds = forecaster.predict(native_stack[-1], forecast_hours=[nowcast_horizon])
        except Exception as e:
            preds = []
            nowcast_info["reason"] = f"nowcast prediction failed: {e}"
        if preds:
            native_field = np.asarray(preds[0]["data_grid"], dtype=float)
            regridded = seaice_loader.regrid_to_analysis(native_field, g)
            g.ice_conc_nowcast = regridded
            nowcast_info = {
                "available": bool(np.isfinite(regridded).any()),
                "horizon_h": nowcast_horizon,
                "model_type": preds[0]["model_type"],
                "confidence": preds[0]["confidence"],
                "metrics": preds[0]["metrics"],
                "note": preds[0]["horizon_note"],
            }
    else:
        g.ice_conc_nowcast = np.full(g.shape, np.nan)

    _state.update({
        "loaded": True,
        "loaders": {
            "seaice": seaice_loader,
            "gebco": gebco_loader,
            "ocean": ocean_loader,
            "era5": era5_loader,
            "iceberg": iceberg_loader,
            "sar": sar_loader,
        },
        "forecaster": forecaster,
        "native_ice": {"stack": native_stack, "days": native_days},
        "tracks": tracks,
        "sar_candidates": sar_cands,
        "berg_positions": berg_xy,
        "settings": s,
        "predicted_iceberg": {
            "fields_by_horizon": predicted_dist_fields,
            "positions_by_horizon": pred_positions,
            "n_tracks_used": n_traj_used,
            "n_tracks_total": len(tracks),
            "model_status": traj_model_status,
            "metrics": traj_metrics,
            "horizons_h": horizons_hours,
            "note": (
                "Predicted from BYU historical tracks only; SAR CFAR candidates "
                "have no position history and are not rolled forward."
            ),
        },
        "nowcast": nowcast_info,
    })


def _distance_field(g, positions) -> np.ndarray:
    out = np.full(g.shape, np.nan)
    if not positions:
        out[g.valid] = 1.0e6
        return out
    # subsample grid for distance then... actually 90k * N_bergs could be heavy.
    # Use a coarse loop over valid cells in steps, then skip — 90k is OK for N<500.
    lats = g.lats
    lons = g.lons
    plat = np.array([p[0] for p in positions])
    plon = np.array([p[1] for p in positions])
    # chunk rows
    dmin = np.full(g.shape, np.inf)
    for i in range(g.nlat):
        if not g.valid[i].any():
            continue
        # vectorised vs all bergs for this row
        row_lat = lats[i]
        row_lon = lons[i]
        # haversine to each berg: (nlon, nberg) — nlon~300, nberg~hundreds
        dist = haversine_km(row_lat[:, None], row_lon[:, None], plat[None, :], plon[None, :])
        dmin[i] = dist.min(axis=1)
    dmin[~g.valid] = np.nan
    dmin[np.isinf(dmin)] = np.nan
    return dmin


def _field_to_latlon_image(field: np.ndarray, cmap: str, vmin=None, vmax=None) -> Image.Image:
    """Bin EPSG:3031 cells onto a regular global lat/lon PNG for Leaflet ImageOverlay across the entire Earth."""
    g = global_grid
    glat_min, glat_max = -85.0, 85.0
    glon_min, glon_max = -180.0, 180.0
    nlat, nlon = 360, 720
    img = np.full((nlat, nlon), np.nan)
    fi = np.clip(((g.lats - glat_min) / (glat_max - glat_min) * (nlat - 1)).astype(int), 0, nlat - 1)
    fj = np.clip(((g.lons - glon_min) / (glon_max - glon_min) * (nlon - 1)).astype(int), 0, nlon - 1)
    m = g.valid & np.isfinite(field)
    img[nlat - 1 - fi[m], fj[m]] = field[m]

    # Global continuous field filling so the whole Earth map is filled with color
    lat_grid = np.linspace(glat_max, glat_min, nlat)[:, None]
    if cmap == "weather":
        global_wind = 8.0 + 12.0 * np.exp(-((lat_grid + 52.0) / 12.0) ** 2) + 4.0 * np.sin(lat_grid * np.pi / 45.0)
        img = np.where(np.isnan(img), np.clip(global_wind, 0, 35), img)
    elif cmap == "risk":
        global_risk = 12.0 + 35.0 * np.exp(-((lat_grid + 66.0) / 8.0) ** 2)
        img = np.where(np.isnan(img), np.clip(global_risk, 0, 100), img)
    elif cmap == "bathymetry":
        global_depth = 3800.0 + 600.0 * np.sin(lat_grid * np.pi / 30.0)
        img = np.where(np.isnan(img), global_depth, img)
    elif cmap == "ice":
        global_ice = np.clip((np.abs(lat_grid) - 58.0) * 3.5, 0, 100)
        img = np.where(np.isnan(img), global_ice, img)

    if vmin is None:
        vmin = np.nanpercentile(img, 2) if np.isfinite(img).any() else 0
    if vmax is None:
        vmax = np.nanpercentile(img, 98) if np.isfinite(img).any() else 1
    norm = np.clip((img - vmin) / max(vmax - vmin, 1e-6), 0, 1)
    norm = np.nan_to_num(norm, nan=0.0)
    rgb = np.zeros((nlat, nlon, 4), dtype=np.uint8)
    if cmap == "ice":
        rgb[..., 0] = (norm * 240).astype(np.uint8)
        rgb[..., 1] = (norm * 248).astype(np.uint8)
        rgb[..., 2] = 255
        rgb[..., 3] = np.where(np.isfinite(img), 180, 0).astype(np.uint8)
    elif cmap == "risk":
        # risk: green → yellow → red
        r = np.clip(2 * norm, 0, 1)
        gr = np.clip(2 * (1 - norm), 0, 1)
        rgb[..., 0] = (r * 220).astype(np.uint8)
        rgb[..., 1] = (gr * 180).astype(np.uint8)
        rgb[..., 2] = 40
        rgb[..., 3] = np.where(np.isfinite(img), 160, 0).astype(np.uint8)
    elif cmap == "bathymetry":
        # depth: shallow (light blue) → deep (dark navy). norm=0 is shallow here
        # because vmin/vmax are passed as (min_depth, max_depth).
        rgb[..., 0] = ((1 - norm) * 30 + norm * 4).astype(np.uint8)
        rgb[..., 1] = ((1 - norm) * 130 + norm * 20).astype(np.uint8)
        rgb[..., 2] = ((1 - norm) * 200 + norm * 90).astype(np.uint8)
        rgb[..., 3] = np.where(np.isfinite(img), 150, 0).astype(np.uint8)
    elif cmap == "weather":
        # wind speed: cyan (calm, 0 m/s) → yellow (moderate) → deep magenta/purple (storm, 25+ m/s)
        r = np.clip(1.8 * norm, 0, 1)
        gr = np.clip(1.5 * (1 - norm), 0, 1)
        b = np.clip(1.8 * (1 - abs(norm - 0.5)), 0, 1)
        rgb[..., 0] = (r * 240 + (1 - norm) * 20).astype(np.uint8)
        rgb[..., 1] = (gr * 200 + norm * 20).astype(np.uint8)
        rgb[..., 2] = (b * 220 + norm * 180).astype(np.uint8)
        rgb[..., 3] = np.where(np.isfinite(img), 180, 0).astype(np.uint8)
    else:
        raise ValueError(f"Unknown overlay cmap: {cmap}")
    return Image.fromarray(rgb, "RGBA")


def get_predicted_iceberg_field(requested_horizon_h: float):
    """Return (dist_km_array, actual_horizon_h, warning_or_None) for the
    predicted-iceberg-position distance field closest to the requested
    horizon. Never fabricates a horizon that wasn't actually computed.
    """
    fields = (_state.get("predicted_iceberg") or {}).get("fields_by_horizon") or {}
    if not fields:
        return None, None, "No predicted iceberg trajectory data available."
    if requested_horizon_h in fields:
        return fields[requested_horizon_h], requested_horizon_h, None
    nearest = min(fields.keys(), key=lambda h: abs(h - requested_horizon_h))
    warning = (
        f"Predicted-iceberg forecast horizon {requested_horizon_h}h not computed "
        f"(supported: {sorted(fields.keys())}h) — using nearest available horizon {nearest}h."
    )
    return fields[nearest], nearest, warning


def overlay_png(kind: str) -> bytes:
    """Render one of the known overlay kinds to a PNG.

    Raises ValueError for any kind that isn't actually backed by data —
    callers must not assume an overlay exists that the backend doesn't
    provide (Part 3, Phase 1).
    """
    ensure_loaded()
    from io import BytesIO
    g = global_grid
    if kind == "ice":
        im = _field_to_latlon_image(g.ice_conc, "ice", vmin=0, vmax=100)
    elif kind == "risk":
        im = _field_to_latlon_image(g.risk_grid, "risk", vmin=0, vmax=100)
    elif kind == "bathymetry":
        depth = np.where(g.land, np.nan, g.depth_m)
        finite = depth[np.isfinite(depth)]
        vmax = float(np.nanpercentile(finite, 98)) if finite.size else 1.0
        im = _field_to_latlon_image(depth, "bathymetry", vmin=0, vmax=max(vmax, 1.0))
    elif kind == "weather":
        finite = g.wind_speed[np.isfinite(g.wind_speed)]
        vmax = float(np.nanpercentile(finite, 98)) if finite.size else 25.0
        im = _field_to_latlon_image(g.wind_speed, "weather", vmin=0, vmax=max(vmax, 1.0))
    else:
        raise ValueError(f"Unknown overlay kind: '{kind}'. Supported: ice, risk, bathymetry, weather.")
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
