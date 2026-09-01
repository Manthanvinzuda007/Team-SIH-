"""GEBCO bathymetry loader.

Real data: gebco_2026_n-50.0_s-75.0_w-180.0_e180.0.nc, ~990 MB, 6000x86400 grid.
Variable 'elevation' (negative = depth below sea level, positive = land).
NEVER load the full array into memory. Use windowed reads via netCDF4 index slicing.
"""
import os
import logging
from typing import Dict, Any, Optional

import numpy as np
import netCDF4

from app.data_ingestion.base_loader import BaseLoader
from app.core.geo import field_stats, sample_regular_latlon

logger = logging.getLogger("polaris.gebco")


class GebcoLoader(BaseLoader):
    """Load GEBCO elevation data using windowed reads."""

    def __init__(self, dataset_path: str):
        super().__init__(dataset_path)
        self.dataset_name = "GEBCO Bathymetry"
        self.dataset_type = "GEBCO"
        self.files = self.search_files(["*.nc"])

    def validate_file(self, filepath: str) -> bool:
        try:
            nc = netCDF4.Dataset(filepath)
            ok = "elevation" in nc.variables
            nc.close()
            return ok
        except Exception:
            return False

    def parse_metadata(self, filepath: str) -> Dict[str, Any]:
        try:
            nc = netCDF4.Dataset(filepath)
            lat = nc.variables["lat"]
            lon = nc.variables["lon"]
            meta = {
                "lat_range": [float(lat[0]), float(lat[-1])],
                "lon_range": [float(lon[0]), float(lon[-1])],
                "lat_shape": lat.shape[0],
                "lon_shape": lon.shape[0],
                "valid": True,
            }
            nc.close()
            return meta
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def load(self, filepath: str):
        """Not used directly — use load_depth_on_grid instead."""
        pass

    def load_depth_on_grid(self, grid) -> np.ndarray:
        """Sample GEBCO elevation onto the analysis grid using windowed index slicing.

        Returns depth in meters (positive down). Land cells get NaN.
        """
        if not self.files:
            logger.warning("No GEBCO files found")
            return np.full(grid.grid_shape, np.nan)

        fp = self.files[0]
        logger.info("Loading GEBCO from %s (windowed)", fp)

        nc = netCDF4.Dataset(fp)
        lat_all = nc.variables["lat"][:]
        lon_all = nc.variables["lon"][:]

        # Find index window covering the analysis grid bounds with margin
        lat_min = float(grid.lats[np.isfinite(grid.lats)].min()) - 1.0
        lat_max = float(grid.lats[np.isfinite(grid.lats)].max()) + 1.0
        lon_min = float(grid.lons[np.isfinite(grid.lons)].min()) - 1.0
        lon_max = float(grid.lons[np.isfinite(grid.lons)].max()) + 1.0

        lat_idx = np.where((lat_all >= lat_min) & (lat_all <= lat_max))[0]
        lon_idx = np.where((lon_all >= lon_min) & (lon_all <= lon_max))[0]

        if len(lat_idx) == 0 or len(lon_idx) == 0:
            logger.error("GEBCO window empty for bounds lat[%.1f,%.1f] lon[%.1f,%.1f]",
                         lat_min, lat_max, lon_min, lon_max)
            nc.close()
            return np.full(grid.grid_shape, np.nan)

        i0, i1 = int(lat_idx[0]), int(lat_idx[-1]) + 1
        j0, j1 = int(lon_idx[0]), int(lon_idx[-1]) + 1

        logger.info("GEBCO window: lat[%d:%d] lon[%d:%d] = %dx%d",
                     i0, i1, j0, j1, i1 - i0, j1 - j0)

        # Subsample to manageable size: take every Nth point so we get ~500x500
        step = max(1, max((i1 - i0) // 500, (j1 - j0) // 500))
        lat_sub = lat_all[i0:i1:step]
        lon_sub = lon_all[j0:j1:step]
        elev_sub = nc.variables["elevation"][i0:i1:step, j0:j1:step]

        nc.close()

        logger.info("GEBCO subsampled to %s (step=%d)", elev_sub.shape, step)

        # Interpolate onto analysis grid
        result = sample_regular_latlon(lat_sub, lon_sub, elev_sub,
                                       grid.lats, grid.lons, fill=np.nan)

        # Convert: GEBCO elevation (negative = depth). We want depth positive-down.
        depth = -result.copy()
        depth[result > 0] = np.nan  # land → NaN

        field_stats("gebco_depth_m", depth)
        return depth

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "name": self.dataset_name,
            "type": self.dataset_type,
            "status": "READY" if self.files else "UNAVAILABLE",
            "files_found": len(self.files),
            "note": "GEBCO 2026, ~15 arc-sec, windowed reads. 50-75S clip.",
        }
