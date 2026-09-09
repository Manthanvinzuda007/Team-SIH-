"""Shared analysis grid.

Design (not a skill score): EPSG:3031 cell centres at GRID_RESOLUTION_KM covering the
configured lat/lon AOI. Native AMSR2 in this bundle is 25 km (EPSG:3412, 316 x 332);
GEBCO is ~15 arc-sec. 10 km is a runnable compromise for interactive A*.

The Leaflet frontend uses Web Mercator; cell centres are also stored as WGS84 lat/lon
for API overlays. This is not a claim that the demo is a polar-stereo tiled map.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
from pyproj import Transformer

from app.core.config import get_settings
from app.core.geo import field_stats


class AnalysisGrid:
    def __init__(self):
        s = get_settings()
        self.lat_min = float(s.ANALYSIS_LAT_MIN)
        self.lat_max = float(s.ANALYSIS_LAT_MAX)
        self.lon_min = float(s.ANALYSIS_LON_MIN)
        self.lon_max = float(s.ANALYSIS_LON_MAX)
        self.resolution_km = float(s.GRID_RESOLUTION_KM)
        self.crs = s.ANALYSIS_CRS

        fwd = Transformer.from_crs("EPSG:4326", "EPSG:3031", always_xy=True)
        inv = Transformer.from_crs("EPSG:3031", "EPSG:4326", always_xy=True)

        lons_b = np.linspace(self.lon_min, self.lon_max, 80)
        lats_b = np.linspace(self.lat_min, self.lat_max, 40)
        xs, ys = [], []
        for la in (self.lat_min, self.lat_max):
            x, y = fwd.transform(lons_b, np.full_like(lons_b, la))
            xs.append(x)
            ys.append(y)
        for lo in (self.lon_min, self.lon_max):
            x, y = fwd.transform(np.full_like(lats_b, lo), lats_b)
            xs.append(x)
            ys.append(y)
        xs = np.concatenate(xs)
        ys = np.concatenate(ys)
        self.x_min, self.x_max = float(xs.min()), float(xs.max())
        self.y_min, self.y_max = float(ys.min()), float(ys.max())

        step = self.resolution_km * 1000.0
        self.xs = np.arange(self.x_min, self.x_max + step * 0.5, step)
        self.ys = np.arange(self.y_max, self.y_min - step * 0.5, -step)  # north-up rows
        self.X, self.Y = np.meshgrid(self.xs, self.ys)
        self.lons, self.lats = inv.transform(self.X, self.Y)
        self.lats = np.asarray(self.lats)
        self.lons = np.asarray(self.lons)

        self.valid = (
            (self.lats >= self.lat_min) & (self.lats <= self.lat_max)
            & (self.lons >= self.lon_min) & (self.lons <= self.lon_max)
        )
        self.grid_shape = self.lats.shape
        nlat, nlon = self.grid_shape
        self.nlat, self.nlon = nlat, nlon

        self.ice_conc = np.full(self.grid_shape, np.nan)       # percent 0-100
        self.depth_m = np.full(self.grid_shape, np.nan)        # positive down
        self.elevation_m = np.full(self.grid_shape, np.nan)    # GEBCO sign convention
        self.uo = np.full(self.grid_shape, np.nan)
        self.vo = np.full(self.grid_shape, np.nan)
        self.u10 = np.full(self.grid_shape, np.nan)
        self.v10 = np.full(self.grid_shape, np.nan)
        self.wind_speed = np.full(self.grid_shape, np.nan)
        self.t2m = np.full(self.grid_shape, np.nan)
        self.msl = np.full(self.grid_shape, np.nan)
        self.iceberg_dist_km = np.full(self.grid_shape, np.nan)
        self.risk_grid = np.full(self.grid_shape, np.nan)
        self.land = np.zeros(self.grid_shape, dtype=bool)

        # -- Part 2 additions --
        self.current_speed = np.full(self.grid_shape, np.nan)          # m/s, |uo,vo|
        # Distance (km) to nearest LSTM-predicted iceberg position, at the
        # horizon currently active in risk_components (see risk_service.py).
        self.predicted_iceberg_dist_km = np.full(self.grid_shape, np.nan)
        self.predicted_iceberg_horizon_h: Optional[float] = None
        self.predicted_iceberg_uncertainty_km: Optional[float] = None
        # Optical-flow sea-ice nowcast, regridded onto this analysis grid
        # (percent 0-100), at SEA_ICE_NOWCAST_RISK_HORIZON_H. NaN/unset when
        # the 8-day corpus can't support advection (see pipeline.py).
        self.ice_conc_nowcast = np.full(self.grid_shape, np.nan)
        # Per-component *weighted* risk contributions (each already scaled by
        # its RISK_WEIGHT_*, so they sum to risk_grid exactly). Populated by
        # RiskService.generate_risk_map(); used for explainable per-route
        # breakdowns in route_service.py. Empty until first computed.
        self.risk_components: Dict[str, np.ndarray] = {}

        field_stats("analysis_grid_lat", self.lats, extra={"crs": self.crs, "res_km": self.resolution_km})

    @property
    def shape(self):
        return self.grid_shape

    def latlon_to_indices(self, lat: float, lon: float):
        """Nearest valid cell in EPSG:3031."""
        fwd = Transformer.from_crs("EPSG:4326", "EPSG:3031", always_xy=True)
        x, y = fwd.transform(lon, lat)
        j = int(np.round((x - self.xs[0]) / (self.xs[1] - self.xs[0])))
        i = int(np.round((self.ys[0] - y) / (self.ys[0] - self.ys[1])))
        if 0 <= i < self.nlat and 0 <= j < self.nlon and self.valid[i, j]:
            return i, j
        # search small neighbourhood for a valid cell
        if 0 <= i < self.nlat and 0 <= j < self.nlon:
            for r in range(1, 6):
                i0, i1 = max(0, i - r), min(self.nlat, i + r + 1)
                j0, j1 = max(0, j - r), min(self.nlon, j + r + 1)
                sub = np.argwhere(self.valid[i0:i1, j0:j1])
                if len(sub):
                    ii, jj = sub[0]
                    return int(i0 + ii), int(j0 + jj)
        return None, None

    def get_risk_at(self, lat: float, lon: float) -> float:
        i, j = self.latlon_to_indices(lat, lon)
        if i is None:
            return 100.0
        v = self.risk_grid[i, j]
        return float(v) if np.isfinite(v) else 100.0

    def bounds_4326(self):
        return {
            "lat_min": self.lat_min,
            "lat_max": self.lat_max,
            "lon_min": self.lon_min,
            "lon_max": self.lon_max,
        }


# Singleton — rebuilt from settings at import
global_grid = AnalysisGrid()
