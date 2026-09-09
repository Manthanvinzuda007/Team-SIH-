"""Classical CFAR-style iceberg candidates from the single Sentinel-1 GRD HH scene.

This is the actual detector deliverable. A YOLO fine-tune on n≈handful of boxes
from one scene would not support a reported precision/recall; none is claimed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import numpy as np
from scipy.ndimage import gaussian_filter, label, maximum_filter, uniform_filter

from app.core.geo import field_stats
from app.data_ingestion.sentinel1_loader import Sentinel1Loader, rowcol_to_ll

logger = logging.getLogger("polaris")


class CFARDetector:
    def detect_from_preview(self, preview: Dict[str, Any], min_db: float = -2.0,
                            k_sigma: float = 4.0, min_pixels: int = 2,
                            max_pixels: int = 400) -> List[Dict[str, Any]]:
        db = preview.get("sigma0_db")
        if db is None:
            return []
        geo = preview["geo"]
        stride = int(preview.get("stride", 20))
        valid = np.isfinite(db)
        clutter = uniform_filter(np.nan_to_num(db, nan=-25.0), size=31)
        std = np.sqrt(np.maximum(uniform_filter((np.nan_to_num(db, nan=-25.0) - clutter) ** 2, size=31), 1e-6))
        bright = valid & (db > clutter + k_sigma * std) & (db > min_db)
        # compact peaks vs diffuse sea-ice texture
        local_max = db == maximum_filter(np.nan_to_num(db, nan=-99), size=5)
        seeds = bright & local_max
        labeled, nlab = label(bright)
        cands = []
        h, w = db.shape
        for lab_id in range(1, nlab + 1):
            ys, xs = np.where(labeled == lab_id)
            if ys.size < min_pixels or ys.size > max_pixels:
                continue
            if not np.any(seeds[ys, xs]):
                continue
            # centroid in preview pixels → original row/col
            py, px = float(ys.mean()), float(xs.mean())
            row = py * stride
            col = px * stride
            lat, lon = rowcol_to_ll(geo, np.array([row]), np.array([col]))
            lat, lon = float(lat[0]), float(lon[0])
            peak = float(np.nanmax(db[ys, xs]))
            # brightness score 0-1 from sigma0 dB relative to threshold
            conf = float(np.clip((peak - min_db) / 20.0, 0.05, 0.99))
            cands.append({
                "lat": lat, "lon": lon, "sigma0_db": peak,
                "confidence": conf, "n_pixels_preview": int(ys.size),
                "source": "S1_CFAR",
            })
        # keep top N by brightness to avoid thousands of speckle hits
        cands.sort(key=lambda c: c["sigma0_db"], reverse=True)
        cands = cands[:200]
        field_stats("S1_CFAR_sigma0_db", np.array([c["sigma0_db"] for c in cands]) if cands else np.array([np.nan]))
        logger.info("CFAR candidates=%s (single scene, no labelled precision)", len(cands))
        return cands


class YOLODetector:
    """Not trained. One unlabeled scene is not a detection benchmark."""

    def detect(self, sar_image_path):
        return []


class IcebergDetector:
    def __init__(self):
        self.model_status = "CFAR"
        self.model = CFARDetector()

    def detect(self, loader: Sentinel1Loader, stride: int = 16) -> List[Dict[str, Any]]:
        preview = loader.load_calibrated_preview(stride=stride)
        if not preview:
            return []
        return self.model.detect_from_preview(preview)
