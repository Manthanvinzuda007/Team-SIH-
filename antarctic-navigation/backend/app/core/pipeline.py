"""Load all real fields onto the shared analysis grid (once per process)."""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

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

logger = logging.getLogger("polaris")
_lock = threading.Lock()
_state: Dict[str, Any] = {"loaded": False}


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
        _load(include_sar=include_sar)
        return _state


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

    # -- ERA5 weather --
    era5_loader = EnvironmentLoader(str(s.dataset_dir / "ERA5_Dtaset"))
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
    """Bin EPSG:3031 cells onto a regular lat/lon PNG for Leaflet ImageOverlay."""
    g = global_grid
    nlat, nlon = 180, 320
    img = np.full((nlat, nlon), np.nan)
    counts = np.zeros((nlat, nlon))
    fi = np.clip(((g.lats - g.lat_min) / (g.lat_max - g.lat_min) * (nlat - 1)).astype(int), 0, nlat - 1)
    fj = np.clip(((g.lons - g.lon_min) / (g.lon_max - g.lon_min) * (nlon - 1)).astype(int), 0, nlon - 1)
    m = g.valid & np.isfinite(field)
    # last-write bin (adequate for overlay)
    img[nlat - 1 - fi[m], fj[m]] = field[m]
    if vmin is None:
        vmin = np.nanpercentile(field[m], 2) if m.any() else 0
    if vmax is None:
        vmax = np.nanpercentile(field[m], 98) if m.any() else 1
    norm = np.clip((img - vmin) / max(vmax - vmin, 1e-6), 0, 1)
    rgb = np.zeros((nlat, nlon, 4), dtype=np.uint8)
    if cmap == "ice":
        rgb[..., 0] = (norm * 240).astype(np.uint8)
        rgb[..., 1] = (norm * 248).astype(np.uint8)
        rgb[..., 2] = 255
        rgb[..., 3] = np.where(np.isfinite(img), 180, 0).astype(np.uint8)
    else:
        # risk: green → yellow → red
        r = np.clip(2 * norm, 0, 1)
        gr = np.clip(2 * (1 - norm), 0, 1)
        rgb[..., 0] = (r * 220).astype(np.uint8)
        rgb[..., 1] = (gr * 180).astype(np.uint8)
        rgb[..., 2] = 40
        rgb[..., 3] = np.where(np.isfinite(img), 160, 0).astype(np.uint8)
    return Image.fromarray(rgb, "RGBA")


def overlay_png(kind: str) -> bytes:
    ensure_loaded()
    from io import BytesIO
    g = global_grid
    if kind == "ice":
        im = _field_to_latlon_image(g.ice_conc, "ice", vmin=0, vmax=100)
    else:
        im = _field_to_latlon_image(g.risk_grid, "risk", vmin=0, vmax=100)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
