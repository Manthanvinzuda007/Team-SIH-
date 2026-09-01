"""Geographic helpers. Distances are haversine on WGS84; no fabricated CRS claims."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger("polaris")

R_KM = 6371.0
R_NM = 3440.065


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * R_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    return float(haversine_km(lat1, lon1, lat2, lon2) * 1000.0 / 1852.0)


def field_stats(name: str, arr: np.ndarray, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    a = np.asarray(arr)
    if a.size == 0:
        stats: Dict[str, Any] = {"name": name, "shape": list(a.shape), "count": 0, "finite": 0, "nan_frac": 1.0,
                                 "min": None, "max": None, "mean": None}
    else:
        af = a.astype(np.float64, copy=False)
        finite = np.isfinite(af)
        nf = int(finite.sum())
        stats = {
            "name": name,
            "shape": list(a.shape),
            "count": int(a.size),
            "finite": nf,
            "nan_frac": float(1.0 - nf / max(a.size, 1)),
            "min": float(np.nanmin(af)) if nf else None,
            "max": float(np.nanmax(af)) if nf else None,
            "mean": float(np.nanmean(af)) if nf else None,
        }
    if extra:
        stats.update(extra)
    logger.info(
        "FIELD %s shape=%s min=%s max=%s mean=%s nan_frac=%.4f finite=%s/%s",
        name, stats["shape"], stats["min"], stats["max"], stats["mean"],
        stats["nan_frac"], stats["finite"], stats["count"],
    )
    return stats


def increasing_axis(coord: np.ndarray, values: np.ndarray):
    """RegularGridInterpolator requires monotonically increasing axes."""
    c = np.asarray(coord)
    v = np.asarray(values)
    if c[0] > c[-1]:
        return c[::-1].copy(), np.flip(v, axis=0)
    return c, v


def sample_regular_latlon(lat: np.ndarray, lon: np.ndarray, values: np.ndarray,
                          qlat: np.ndarray, qlon: np.ndarray, fill=np.nan) -> np.ndarray:
    """Bilinear sample of a regular lat/lon array at query points. lat/lon are 1-D."""
    from scipy.interpolate import RegularGridInterpolator

    lat = np.asarray(lat)
    lon = np.asarray(lon)
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError(f"expected 2-D field, got {values.shape}")

    lat_ax, vals = increasing_axis(lat, values)
    lon_ax = np.asarray(lon)
    if lon_ax[0] > lon_ax[-1]:
        lon_ax = lon_ax[::-1].copy()
        vals = np.flip(vals, axis=1)

    interp = RegularGridInterpolator(
        (lat_ax, lon_ax), vals, bounds_error=False, fill_value=fill
    )
    pts = np.column_stack([np.ravel(qlat), np.ravel(qlon)])
    out = interp(pts)
    return out.reshape(np.shape(qlat))
