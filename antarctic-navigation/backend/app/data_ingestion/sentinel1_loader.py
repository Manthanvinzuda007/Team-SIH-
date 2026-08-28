"""Sentinel-1 SAR GRD HH loader.

Real data: 1 scene, IW mode, HH polarization, 25114x13278 uint16.
No embedded CRS in the TIFF (bounds are pixel coords).
Geographic footprint parsed from annotation XML geolocation grid points.
Calibration LUT available in calibration-*.xml for DN->sigma0 conversion.

This is one scene, single pol, single date. Do NOT claim multi-temporal change detection.
"""
import os
import logging
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET

import numpy as np

from app.data_ingestion.base_loader import BaseLoader

logger = logging.getLogger("polaris.sentinel1")


def rowcol_to_ll(geo: Dict[str, Any], rows: np.ndarray, cols: np.ndarray):
    """Map (row, col) in the GRD image to (lat, lon) via the annotation geolocation grid.

    `geo` is a dict with 'rows', 'cols', 'lats', 'lons' arrays from the annotation XML.
    Uses bilinear interpolation on the sparse geolocation grid.
    """
    from scipy.interpolate import RegularGridInterpolator

    grow = np.array(geo["rows"])
    gcol = np.array(geo["cols"])
    glat = np.array(geo["lats"]).reshape(len(grow), len(gcol))
    glon = np.array(geo["lons"]).reshape(len(grow), len(gcol))

    lat_interp = RegularGridInterpolator((grow, gcol), glat, bounds_error=False, fill_value=None)
    lon_interp = RegularGridInterpolator((grow, gcol), glon, bounds_error=False, fill_value=None)

    pts = np.column_stack([np.ravel(rows), np.ravel(cols)])
    lats = lat_interp(pts)
    lons = lon_interp(pts)
    return lats, lons


class Sentinel1Loader(BaseLoader):
    """Load Sentinel-1 SAFE product."""

    def __init__(self, dataset_path: str):
        super().__init__(dataset_path)
        self.dataset_name = "Sentinel-1 SAR"
        self.dataset_type = "SENTINEL1"
        self.safe_dir = dataset_path
        self.files = self._find_tiffs()
        self._geo: Optional[Dict[str, Any]] = None
        self._cal_lut: Optional[Dict[str, Any]] = None

    def _find_tiffs(self):
        meas_dir = os.path.join(self.safe_dir, "measurement")
        if os.path.isdir(meas_dir):
            return [os.path.join(meas_dir, f) for f in os.listdir(meas_dir) if f.endswith(".tiff")]
        return []

    def validate_file(self, filepath: str) -> bool:
        return filepath.endswith(".tiff") and os.path.exists(filepath)

    def parse_metadata(self, filepath: str = None) -> Dict[str, Any]:
        return {"valid": bool(self.files), "tiff_files": len(self.files)}

    def load(self, filepath: str = None):
        pass

    def _parse_geolocation_grid(self) -> Optional[Dict[str, Any]]:
        """Parse geolocation grid from annotation XML."""
        if self._geo is not None:
            return self._geo

        ann_dir = os.path.join(self.safe_dir, "annotation")
        if not os.path.isdir(ann_dir):
            return None

        for f in os.listdir(ann_dir):
            if f.endswith(".xml") and not f.startswith("calibration") and not f.startswith("noise") and not f.startswith("rfi"):
                ann_path = os.path.join(ann_dir, f)
                try:
                    tree = ET.parse(ann_path)
                    root = tree.getroot()

                    # Try with and without namespace
                    geo_pts = root.findall(".//{*}geolocationGridPoint")
                    if not geo_pts:
                        geo_pts = root.findall(".//geolocationGridPoint")

                    if not geo_pts:
                        continue

                    rows_set = set()
                    cols_set = set()
                    data = []
                    for p in geo_pts:
                        def _text(tag):
                            el = p.find(f"{{{p.tag.split('}')[0][1:]}}}{tag}" if '}' in p.tag else tag)
                            if el is None:
                                el = p.find(f"{{*}}{tag}")
                            if el is None:
                                el = p.find(tag)
                            return el.text if el is not None else None

                        line = _text("line")
                        pixel = _text("pixel")
                        lat = _text("latitude")
                        lon = _text("longitude")
                        if all(x is not None for x in [line, pixel, lat, lon]):
                            r, c = float(line), float(pixel)
                            rows_set.add(r)
                            cols_set.add(c)
                            data.append((r, c, float(lat), float(lon)))

                    rows = sorted(rows_set)
                    cols = sorted(cols_set)
                    nr, nc = len(rows), len(cols)

                    lats = np.zeros((nr, nc))
                    lons = np.zeros((nr, nc))
                    row_idx = {r: i for i, r in enumerate(rows)}
                    col_idx = {c: j for j, c in enumerate(cols)}
                    for r, c, la, lo in data:
                        lats[row_idx[r], col_idx[c]] = la
                        lons[row_idx[r], col_idx[c]] = lo

                    self._geo = {
                        "rows": rows,
                        "cols": cols,
                        "lats": lats.ravel().tolist(),
                        "lons": lons.ravel().tolist(),
                        "lat_min": float(lats.min()),
                        "lat_max": float(lats.max()),
                        "lon_min": float(lons.min()),
                        "lon_max": float(lons.max()),
                    }
                    logger.info("Parsed SAR geolocation grid: %dx%d pts, lat[%.2f,%.2f] lon[%.2f,%.2f]",
                                nr, nc, self._geo["lat_min"], self._geo["lat_max"],
                                self._geo["lon_min"], self._geo["lon_max"])
                    return self._geo
                except Exception as e:
                    logger.warning("Failed to parse annotation %s: %s", f, e)
        return None

    def _parse_calibration_lut(self) -> Optional[np.ndarray]:
        """Parse sigma0 calibration LUT from calibration XML. Returns 1-D sigma0LUT."""
        if self._cal_lut is not None:
            return self._cal_lut

        cal_dir = os.path.join(self.safe_dir, "annotation", "calibration")
        if not os.path.isdir(cal_dir):
            return None

        for f in os.listdir(cal_dir):
            if f.startswith("calibration") and f.endswith(".xml"):
                try:
                    tree = ET.parse(os.path.join(cal_dir, f))
                    root = tree.getroot()
                    # Find sigmaNought vector
                    for vec in root.iter():
                        if "calibrationVector" in vec.tag:
                            sigma_el = None
                            for child in vec:
                                if "sigmaNought" in child.tag:
                                    sigma_el = child
                                    break
                            if sigma_el is not None and sigma_el.text:
                                vals = [float(x) for x in sigma_el.text.strip().split()]
                                self._cal_lut = np.array(vals, dtype=np.float64)
                                logger.info("Parsed calibration LUT: %d values", len(vals))
                                return self._cal_lut
                except Exception as e:
                    logger.warning("Failed to parse calibration %s: %s", f, e)
        return None

    def load_calibrated_preview(self, stride: int = 16) -> Optional[Dict[str, Any]]:
        """Load a strided preview of the GRD scene calibrated to sigma0 (dB).

        Returns dict with 'sigma0_db' (2D array), 'geo' (geolocation grid), 'stride'.
        """
        if not self.files:
            return None

        geo = self._parse_geolocation_grid()
        if geo is None:
            logger.warning("No geolocation grid — cannot geolocate SAR preview")
            return None

        import rasterio

        with rasterio.open(self.files[0]) as src:
            # Read strided
            height = src.height
            width = src.width
            out_h = height // stride
            out_w = width // stride

            dn = src.read(1, out_shape=(out_h, out_w)).astype(np.float64)

        # Calibrate: sigma0 = (DN^2) / (cal_LUT^2)
        # If LUT not available, approximate with simple DN^2 scaling
        cal = self._parse_calibration_lut()
        if cal is not None and len(cal) > 0:
            # Resample LUT to match strided width
            cal_resampled = np.interp(np.linspace(0, len(cal)-1, out_w), np.arange(len(cal)), cal)
            cal_2d = np.tile(cal_resampled, (out_h, 1))
            with np.errstate(divide="ignore", invalid="ignore"):
                sigma0 = (dn ** 2) / (cal_2d ** 2)
        else:
            # Fallback: treat DN as proportional to amplitude
            sigma0 = dn ** 2 / 1e6  # rough scaling

        # Convert to dB
        with np.errstate(divide="ignore"):
            sigma0_db = 10.0 * np.log10(np.maximum(sigma0, 1e-10))

        logger.info("SAR preview: %s, sigma0_db range [%.1f, %.1f]",
                     sigma0_db.shape, np.nanmin(sigma0_db), np.nanmax(sigma0_db))

        return {
            "sigma0_db": sigma0_db,
            "geo": geo,
            "stride": stride,
            "shape_original": (height, width),
        }

    def load_quicklook(self) -> Optional[str]:
        ql = os.path.join(self.safe_dir, "preview", "quick-look.png")
        return ql if os.path.exists(ql) else None

    def get_image_shape(self) -> Optional[tuple]:
        if not self.files:
            return None
        import rasterio
        with rasterio.open(self.files[0]) as src:
            return (src.height, src.width)

    def get_provenance(self) -> Dict[str, Any]:
        geo = self._parse_geolocation_grid()
        return {
            "name": self.dataset_name,
            "type": self.dataset_type,
            "status": "READY" if self.files else "UNAVAILABLE",
            "files_found": len(self.files),
            "footprint": {"lat_min": geo["lat_min"], "lat_max": geo["lat_max"],
                          "lon_min": geo["lon_min"], "lon_max": geo["lon_max"]} if geo else None,
            "note": "1 scene, HH pol, IW GRD. CFAR detection baseline — no trained YOLO precision claim.",
        }
