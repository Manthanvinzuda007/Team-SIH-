"""NSIDC-0803 AMSR2 sea-ice concentration loader.

Real data: 8 NetCDF files (Aug 1-8 2026), variable 'ICECON', polar-stereo grid 316x332.
Values are fraction 0-1 (with occasional >1 due to retrieval artifacts - clamped to 1).
This loader reprojects to the shared lat/lon analysis grid via nearest-neighbour sampling.
"""
import os
import glob
import logging
from typing import Dict, Any, List, Optional

import numpy as np
import xarray as xr
from pyproj import Transformer

from app.data_ingestion.base_loader import BaseLoader
from app.core.geo import field_stats

logger = logging.getLogger("polaris.seaice")


class SeaIceLoader(BaseLoader):
    """Load NSIDC-0803 AMSR2 sea-ice concentration files."""

    CANDIDATE_VARNAMES = ["ICECON", "F17_ICECON", "goddard_merged_seaice_conc",
                          "sea_ice_concentration"]

    def __init__(self, dataset_path: str):
        super().__init__(dataset_path)
        self.dataset_name = "NSIDC AMSR2 Sea Ice"
        self.dataset_type = "NSIDC"
        self.files = sorted(self.search_files(["NSIDC*.nc", "*.nc"]))
        self._varname: Optional[str] = None  # discovered at first load
        self._native_latlon = None  # cached (lats, lons) for native grid, set on first load

    def validate_file(self, filepath: str) -> bool:
        try:
            with xr.open_dataset(filepath) as ds:
                for v in self.CANDIDATE_VARNAMES:
                    if v in ds.data_vars:
                        return True
        except Exception:
            pass
        return False

    def _detect_varname(self, ds: xr.Dataset) -> Optional[str]:
        for v in self.CANDIDATE_VARNAMES:
            if v in ds.data_vars:
                return v
        return None

    def parse_metadata(self, filepath: str) -> Dict[str, Any]:
        try:
            with xr.open_dataset(filepath) as ds:
                vn = self._detect_varname(ds)
                time_val = str(ds.time.values[0]) if "time" in ds.coords else "unknown"
                return {"time": time_val, "variable": vn, "valid": vn is not None}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def load(self, filepath: str) -> Optional[xr.Dataset]:
        return xr.open_dataset(filepath)

    def load_concentration_on_grid(self, grid, time_index: int = -1) -> np.ndarray:
        """Load the latest (or specified) AMSR2 file and sample onto the analysis grid.

        Returns concentration as percent (0-100) on grid.lats/grid.lons.
        """
        if not self.files:
            logger.warning("No AMSR2 files found")
            return np.full(grid.grid_shape, np.nan)

        idx = min(time_index, len(self.files) - 1)
        fp = self.files[idx]
        logger.info("Loading AMSR2 from %s", fp)

        ds = xr.open_dataset(fp)
        vn = self._detect_varname(ds)
        if vn is None:
            logger.error("No known ice-concentration variable in %s", fp)
            ds.close()
            return np.full(grid.grid_shape, np.nan)

        self._varname = vn
        ice = ds[vn].values.squeeze()  # shape (ny, nx)

        # Clamp to [0, 1] then convert to percent
        ice = np.clip(ice, 0.0, 1.0) * 100.0

        # The file is on an NSIDC polar-stereo grid (EPSG:3412 south).
        # Build lat/lon for each pixel, then interpolate to analysis grid.
        x_1d = ds.x.values
        y_1d = ds.y.values
        X, Y = np.meshgrid(x_1d, y_1d)

        # AMSR2 south uses EPSG:3412 (NSIDC Sea Ice Polar Stereographic South)
        to_latlon = Transformer.from_crs("EPSG:3412", "EPSG:4326", always_xy=True)
        src_lons, src_lats = to_latlon.transform(X, Y)
        self._native_latlon = (src_lats, src_lons)

        ds.close()

        # Nearest-neighbour sampling onto analysis grid
        from scipy.interpolate import NearestNDInterpolator
        valid = np.isfinite(ice)
        if valid.sum() == 0:
            return np.full(grid.grid_shape, np.nan)

        pts = np.column_stack([src_lats[valid], src_lons[valid]])
        interp = NearestNDInterpolator(pts, ice[valid])
        result = interp(grid.lats, grid.lons)

        field_stats("ice_concentration_pct", result)
        return result

    def regrid_to_analysis(self, native_field: np.ndarray, grid) -> np.ndarray:
        """Nearest-neighbour sample a field already on the native AMSR2 EPSG:3412
        grid (same shape as ICECON) onto the shared analysis grid.

        Used to bring the optical-flow nowcast (computed on the native grid,
        since the Farneback flow needs native pixel spacing) onto the same
        grid the route-risk engine reads. Requires `load_concentration_on_grid`
        (or `load_all_days`, which does not cache lat/lon) to have been called
        at least once first so native lat/lon are known; returns NaN field
        with a logged warning otherwise rather than guessing a projection.
        """
        if self._native_latlon is None:
            logger.warning("regrid_to_analysis called before native lat/lon were cached — returning NaN")
            return np.full(grid.grid_shape, np.nan)
        src_lats, src_lons = self._native_latlon
        if native_field.shape != src_lats.shape:
            logger.warning(
                "regrid_to_analysis: native_field shape %s != cached native grid shape %s",
                native_field.shape, src_lats.shape,
            )
            return np.full(grid.grid_shape, np.nan)
        from scipy.interpolate import NearestNDInterpolator
        valid = np.isfinite(native_field)
        if valid.sum() == 0:
            return np.full(grid.grid_shape, np.nan)
        pts = np.column_stack([src_lats[valid], src_lons[valid]])
        interp = NearestNDInterpolator(pts, native_field[valid])
        return interp(grid.lats, grid.lons)

    def load_all_days(self) -> List[Dict[str, Any]]:
        """Load all available days, return list of {time, concentration_2d}."""
        days = []
        for fp in self.files:
            ds = xr.open_dataset(fp)
            vn = self._detect_varname(ds)
            if vn is None:
                ds.close()
                continue
            t = str(ds.time.values[0]) if "time" in ds.coords else os.path.basename(fp)
            ice = np.clip(ds[vn].values.squeeze(), 0.0, 1.0) * 100.0
            ds.close()
            days.append({"time": t, "concentration": ice})
        return days

    def get_provenance(self) -> Dict[str, Any]:
        times = []
        for fp in self.files:
            m = self.parse_metadata(fp)
            if m.get("valid"):
                times.append(m["time"])
        return {
            "name": self.dataset_name,
            "type": self.dataset_type,
            "status": "READY" if self.files else "UNAVAILABLE",
            "files_found": len(self.files),
            "variable": self._varname or "(auto-detect on load)",
            "time_range": f"{times[0]} to {times[-1]}" if len(times) >= 2 else str(times),
            "grid_dims": "316x332 polar-stereo (verified)",
            "note": "8 consecutive days only. Insufficient for ConvLSTM training.",
        }
