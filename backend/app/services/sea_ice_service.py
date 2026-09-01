"""Sea ice service — wraps real AMSR2 data loaded by pipeline.

Forecast horizons 6..48h are all provided; the optical-flow model
runs on the native AMSR2 grid and summarises the result numerically.
Full 332×316 grids are NOT returned in JSON — only statistics.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from app.core.grid import global_grid
from app.core.pipeline import ensure_loaded
from app.ml.sea_ice_forecast import SeaIceForecaster

logger = logging.getLogger("polaris.seaice_service")

SUPPORTED_HORIZONS = [6, 12, 18, 24, 30, 36, 42, 48]


class SeaIceService:
    def get_current_ice(self):
        st = ensure_loaded()
        g = global_grid
        step = max(1, int(max(g.nlat, g.nlon) / 50))
        cells = []
        for i in range(0, g.nlat, step):
            for j in range(0, g.nlon, step):
                v = g.ice_conc[i, j]
                if not g.valid[i, j] or not np.isfinite(v):
                    continue
                cells.append({
                    "lat": round(float(g.lats[i, j]), 4),
                    "lon": round(float(g.lons[i, j]), 4),
                    "concentration": round(float(v), 2),
                })

        loader = st["loaders"]["seaice"]
        prov = loader.get_provenance()

        # safe attribute access for timestamps
        time_range = prov.get("time_range", "2026-08-01 to 2026-08-08")
        last_time = time_range.split(" to ")[-1] if " to " in time_range else "2026-08-08"

        return {
            "status": "HISTORICAL",
            "valid_time": last_time,
            "source": "NSIDC-0803 AMSR2 ICECON",
            "units": "percent (0–100); land masked to NaN; ICECON fraction × 100",
            "native_grid": "EPSG:3412 25 km, 332 × 316, 8 days 2026-08-01..08",
            "temporal_status": "HISTORICAL — static file, not a live satellite feed",
            "grid": cells,
            "overlay": {
                "url": "/api/overlays/sea-ice.png",
                "bounds": [[-85.0, -180.0], [85.0, 180.0]],
            },
            "forecast_backtest": st["forecaster"].metrics,
            "provenance": prov,
            "limitation": (
                "Eight daily fields only — 2026-08-01..08. "
                "ConvLSTM was not trained (insufficient data). "
                "Optical-flow advection is the production model."
            ),
        }

    def get_forecast(self, requested_hours: Optional[List[int]] = None):
        st = ensure_loaded()
        native = st["native_ice"]["stack"]
        fc: SeaIceForecaster = st["forecaster"]

        # Validate and clamp requested horizons
        if requested_hours:
            hours = sorted(set(
                h for h in requested_hours
                if 1 <= h <= 48
            ))
            if not hours:
                hours = SUPPORTED_HORIZONS
        else:
            hours = SUPPORTED_HORIZONS

        current_field = native[-1] if native.size else np.zeros((1, 1))
        preds = fc.predict(current_field, hours)

        out = []
        for p in preds:
            grid = np.asarray(p["data_grid"], dtype=float)
            finite = grid[np.isfinite(grid)]
            valid_fraction = finite.size / grid.size if grid.size else 0.0
            out.append({
                "forecast_hour": p["forecast_hour"],
                "model_type": p["model_type"],
                "confidence": round(p["confidence"], 3) if p["confidence"] is not None else None,
                "mean_concentration_fraction": round(float(np.mean(finite)), 4) if finite.size else None,
                "valid_fraction": round(valid_fraction, 4),
                "native_shape": list(grid.shape),
                "metrics": p["metrics"],
                "horizon_note": p["horizon_note"],
                "status": "AVAILABLE",
            })

        # Mark any unsupported horizon explicitly
        out_hours = {o["forecast_hour"] for o in out}
        if requested_hours:
            for h in requested_hours:
                if h not in out_hours:
                    out.append({
                        "forecast_hour": h,
                        "status": "UNAVAILABLE",
                        "reason": f"Horizon {h}h not computable from 8-day AMSR2 corpus",
                    })

        return {
            "requested_hours": hours,
            "forecasts": sorted(out, key=lambda x: x["forecast_hour"]),
            "backtest": fc.metrics,
            "supported_horizons": SUPPORTED_HORIZONS,
            "note": "Nowcast on native AMSR2 grid. Honest horizon ~24–48 h with 8-day corpus.",
            "temporal_status": "HISTORICAL — static 2026-08-08 field as initial condition",
        }
