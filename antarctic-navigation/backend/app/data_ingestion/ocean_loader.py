"""GLORYS/CMEMS ocean current data loader.

Real data: 1 NetCDF (~79 MB), 0.083° daily-mean, variables uo/vo (eastward/northward
sea-water velocity), 8 timesteps, depth=1 (surface), lat 50-75°S, full longitude.
"""
import os
import logging
from typing import Dict, Any, Optional

import numpy as np
import xarray as xr

from app.data_ingestion.base_loader import BaseLoader
from app.core.geo import field_stats, sample_regular_latlon

logger = logging.getLogger("polaris.ocean")


class OceanLoader(BaseLoader):
    """Load GLORYS/CMEMS ocean current reanalysis."""

    def __init__(self, dataset_path: str):
        super().__init__(dataset_path)
        self.dataset_name = "GLORYS Ocean Data"
        self.dataset_type = "GLORYS"
        self.files = self.search_files(["*.nc"])

    def validate_file(self, filepath: str) -> bool:
        try:
            with xr.open_dataset(filepath) as ds:
                return "uo" in ds.data_vars or "vo" in ds.data_vars
        except Exception:
            return False

    def parse_metadata(self, filepath: str) -> Dict[str, Any]:
        try:
            with xr.open_dataset(filepath) as ds:
                return {
                    "variables": list(ds.data_vars),
                    "dims": {k: int(v) for k, v in ds.sizes.items()},
                    "valid": True,
                }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def load(self, filepath: str = None) -> Optional[xr.Dataset]:
        if filepath:
            return xr.open_dataset(filepath)
        if self.files:
            return xr.open_dataset(self.files[0])
        return None

    def load_currents_on_grid(self, grid, time_index: int = -1) -> Dict[str, np.ndarray]:
        """Load uo/vo onto analysis grid.

        Returns dict with 'uo', 'vo', 'current_speed' arrays on grid shape.
        """
        ds = self.load()
        if ds is None:
            logger.warning("No GLORYS data available")
            empty = np.full(grid.grid_shape, np.nan)
            return {"uo": empty, "vo": empty, "current_speed": empty}

        # Select time and depth
        idx = min(time_index, int(ds.sizes.get("time", 1)) - 1)
        snap = ds.isel(time=idx)
        if "depth" in snap.dims:
            snap = snap.isel(depth=0)  # surface

        lat = snap.latitude.values
        lon = snap.longitude.values

        results = {}
        for var in ["uo", "vo"]:
            if var in snap.data_vars:
                vals = snap[var].values.squeeze()
                sampled = sample_regular_latlon(lat, lon, vals, grid.lats, grid.lons)
                results[var] = sampled
                field_stats(f"glorys_{var}", sampled)
            else:
                results[var] = np.full(grid.grid_shape, np.nan)

        results["current_speed"] = np.sqrt(
            np.nan_to_num(results["uo"])**2 + np.nan_to_num(results["vo"])**2
        )
        field_stats("glorys_current_speed", results["current_speed"])

        ds.close()
        return results

    def get_provenance(self) -> Dict[str, Any]:
        return {
            "name": self.dataset_name,
            "type": self.dataset_type,
            "status": "READY" if self.files else "UNAVAILABLE",
            "files_found": len(self.files),
            "note": "GLORYS 0.083° daily-mean ocean currents. Surface uo/vo only.",
        }
