"""ERA5 meteorological data loader.

Real data: two NetCDFs sharing time/lat/lon coordinates:
  - data_stream-oper_stepType-instant.nc: u10, v10, t2m, msl (16 timesteps)
  - data_stream-oper_stepType-accum.nc:  tp (total precip, 16 timesteps)
Both cover 50-90°S, 0.25° resolution, Aug 1-8 2026.
We merge them on the shared time/lat/lon index.
"""
import os
import glob
import logging
from typing import Dict, Any, Optional

import numpy as np
import xarray as xr

from app.data_ingestion.base_loader import BaseLoader
from app.core.geo import field_stats, sample_regular_latlon

logger = logging.getLogger("polaris.era5")


class EnvironmentLoader(BaseLoader):
    """Load ERA5 weather data from split instant/accum NetCDFs."""

    def __init__(self, dataset_path: str):
        super().__init__(dataset_path)
        self.dataset_name = "ERA5 Meteorological Data"
        self.dataset_type = "ERA5"
        self.files = sorted(self.search_files(["*.nc"]))
        self._ds: Optional[xr.Dataset] = None

    def validate_file(self, filepath: str) -> bool:
        try:
            with xr.open_dataset(filepath) as ds:
                return len(ds.data_vars) > 0
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
        """Merge all ERA5 files into one dataset."""
        if not self.files:
            return None
        datasets = []
        for f in self.files:
            try:
                datasets.append(xr.open_dataset(f))
            except Exception as e:
                logger.warning("Cannot open ERA5 file %s: %s", f, e)
        if not datasets:
            return None
        merged = xr.merge(datasets, compat="override")
        logger.info("ERA5 merged: vars=%s, dims=%s", list(merged.data_vars), dict(merged.sizes))
        return merged

    def load_weather_on_grid(self, grid, time_index: int = -1) -> Dict[str, np.ndarray]:
        """Load ERA5 wind/temp/pressure onto analysis grid.

        Returns dict of arrays: u10, v10, wind_speed, t2m, msl, each on grid shape.
        """
        ds = self.load()
        if ds is None:
            logger.warning("No ERA5 data available")
            empty = np.full(grid.grid_shape, np.nan)
            return {"u10": empty, "v10": empty, "wind_speed": empty,
                    "t2m": empty, "msl": empty}

        # Time coordinate may be 'valid_time' (new CDS format) or 'time'
        tname = "valid_time" if "valid_time" in ds.coords else "time"
        idx = min(time_index, int(ds.sizes[tname]) - 1)
        snap = ds.isel({tname: idx})
        logger.info("ERA5 using time index %d: %s", idx, str(snap[tname].values))

        lat = snap.latitude.values
        lon = snap.longitude.values

        results = {}
        for var in ["u10", "v10", "t2m", "msl"]:
            if var in snap.data_vars:
                vals = snap[var].values.squeeze()
                sampled = sample_regular_latlon(lat, lon, vals, grid.lats, grid.lons)
                results[var] = sampled
                field_stats(f"era5_{var}", sampled)
            else:
                results[var] = np.full(grid.grid_shape, np.nan)

        # Wind speed from u10/v10
        results["wind_speed"] = np.sqrt(results["u10"]**2 + results["v10"]**2)
        field_stats("era5_wind_speed", results["wind_speed"])

        ds.close()
        return results

    def get_provenance(self) -> Dict[str, Any]:
        all_vars = set()
        for f in self.files:
            m = self.parse_metadata(f)
            if m.get("valid"):
                all_vars.update(m["variables"])
        return {
            "name": self.dataset_name,
            "type": self.dataset_type,
            "status": "READY" if self.files else "UNAVAILABLE",
            "files_found": len(self.files),
            "variables": sorted(all_vars),
            "note": "ERA5 split instant+accum format. ~16 timesteps Aug 1-8 2026.",
        }
