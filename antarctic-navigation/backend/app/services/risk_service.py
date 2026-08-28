"""Dynamic risk engine — uses REAL loaded data from the pipeline.

Combines:
  - Sea ice concentration from AMSR2 (real)
  - Bathymetry depth from GEBCO (real)
  - Iceberg proximity from BYU tracks + SAR detections (real)
  - Wind severity from ERA5 (real)

Risk = w_ice * f(ice_conc) + w_iceberg * f(distance_to_nearest_berg)
     + w_bathy * f(depth vs draft) + w_weather * f(wind_speed)

No hardcoded lat/lon formulas. Every component reads from global_grid arrays
populated by pipeline.ensure_loaded().
"""
import logging
from typing import Dict, Any, Optional

import numpy as np

from app.core.grid import global_grid
from app.core.config import get_settings
from app.core.geo import field_stats

logger = logging.getLogger("polaris.risk")


class RiskService:
    def __init__(self):
        self.grid = global_grid
        self.settings = get_settings()

    def generate_risk_map(self, weights: Optional[Dict[str, float]] = None,
                          vessel_draft_m: Optional[float] = None) -> Dict[str, Any]:
        """Compute composite risk on the analysis grid from real loaded data.

        Assumes pipeline.ensure_loaded() has already been called (route_service does this).
        """
        from app.core.pipeline import ensure_loaded
        ensure_loaded()

        g = self.grid
        s = self.settings

        w = weights or {
            "ice": s.RISK_WEIGHT_ICE,
            "iceberg": s.RISK_WEIGHT_ICEBERG,
            "weather": s.RISK_WEIGHT_WEATHER,
            "bathymetry": s.RISK_WEIGHT_BATHYMETRY,
        }

        draft = vessel_draft_m or s.DEFAULT_VESSEL_DRAFT_M

        # --- Ice risk: 0-100 based on real AMSR2 concentration ---
        ice = np.nan_to_num(g.ice_conc, nan=0.0)
        ice_risk = np.clip(ice, 0, 100)  # already in percent

        # --- Iceberg proximity risk: from real iceberg_dist_km ---
        dist = np.nan_to_num(g.iceberg_dist_km, nan=9999.0)
        exclusion_km = s.ICEBERG_EXCLUSION_ZONE_NM * 1.852
        # Within exclusion zone → 100, then decays to 0 at 10× exclusion
        berg_risk = np.clip(100.0 * (1.0 - dist / (exclusion_km * 10.0)), 0, 100)
        berg_risk[dist < exclusion_km] = 100.0

        # --- Bathymetry risk: from real GEBCO depth ---
        depth = np.nan_to_num(g.depth_m, nan=0.0)
        margin = s.MIN_DEPTH_MARGIN_M
        safe_depth = draft + margin
        bathy_risk = np.zeros(g.grid_shape)
        shallow = (depth > 0) & (depth < safe_depth * 5)
        bathy_risk[shallow] = np.clip(100.0 * (1.0 - depth[shallow] / (safe_depth * 5)), 0, 100)
        bathy_risk[depth <= safe_depth] = 100.0
        bathy_risk[g.land] = 100.0  # land is impassable

        # --- Weather risk: from real ERA5 wind speed ---
        ws = np.nan_to_num(g.wind_speed, nan=0.0)
        # Scale: 0 m/s → 0 risk, 25 m/s+ → 100 risk
        wx_risk = np.clip(ws / 25.0 * 100.0, 0, 100)

        # --- Composite ---
        total = (w["ice"] * ice_risk
                 + w["iceberg"] * berg_risk
                 + w["bathymetry"] * bathy_risk
                 + w["weather"] * wx_risk)
        total = np.clip(total, 0, 100)
        g.risk_grid = total

        field_stats("composite_risk", total)

        return {
            "resolution_km": g.resolution_km,
            "bounds": g.bounds_4326(),
            "grid_shape": list(g.grid_shape),
            "provenance": {
                "source": "Dynamic Risk Engine — real AMSR2 + GEBCO + ERA5 + BYU/SAR iceberg data",
                "components": ["ice_concentration (AMSR2)", "iceberg_proximity (BYU MERS + SAR CFAR)",
                               "weather (ERA5 wind)", "bathymetry (GEBCO)"],
                "weights": w,
            },
        }

    def calculate_risk(self, lat: float, lon: float, vessel_config=None) -> Dict[str, Any]:
        risk = self.grid.get_risk_at(lat, lon)
        if risk < 25:
            level = "LOW"
        elif risk < 50:
            level = "MODERATE"
        elif risk < 75:
            level = "HIGH"
        else:
            level = "CRITICAL"

        return {
            "risk_score": round(risk, 2),
            "risk_level": level,
        }
