"""Dynamic risk engine — uses REAL loaded data from the pipeline.

Combines:
  - Sea ice concentration from AMSR2, blended with the optical-flow nowcast (real)
  - Bathymetry depth from GEBCO (real)
  - Iceberg proximity from BYU tracks + SAR CFAR candidates, current position (real)
  - Iceberg proximity from LSTM-predicted future positions (forecast, uncertain — Part 2)
  - Wind severity from ERA5 (real)
  - Ocean current speed from GLORYS (real)

risk_grid = w_ice*f(ice) + w_iceberg*f(current_berg, predicted_berg)
          + w_bathy*f(depth vs draft) + w_weather*f(wind) + w_current*f(current_speed)

No hardcoded lat/lon formulas. Every component reads from global_grid arrays
populated by pipeline.ensure_loaded(). Results are cached by (weights, draft,
forecast horizon) so unrelated requests don't recompute the raster
(Part 2 Phase 10) — the cache is cleared whenever the pipeline reloads.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import numpy as np

from app.core.grid import global_grid
from app.core.config import get_settings
from app.core.geo import field_stats

logger = logging.getLogger("polaris.risk")

# Module-level cache: key -> {"risk_grid": arr, "risk_components": dict, "response": dict}
# Deliberately simple (not LRU-bounded) — this is a single-process demo grid,
# not a multi-tenant cache; a handful of weight/horizon combinations in a
# session is the realistic ceiling.
_risk_cache: Dict[tuple, Dict[str, Any]] = {}


def _data_fingerprint(g) -> tuple:
    """Cheap fingerprint of the inputs that affect the risk raster, so the
    cache is invalidated whenever the underlying fields actually change
    (a fresh pipeline load, or — in tests — direct mutation of global_grid)
    without needing an explicit invalidation call from every code path.
    """
    def s(arr):
        finite = arr[np.isfinite(arr)] if arr is not None else np.array([])
        return (float(finite.size), round(float(finite.sum()), 3)) if finite.size else (0.0, 0.0)

    return (
        s(g.ice_conc), s(g.iceberg_dist_km), s(g.predicted_iceberg_dist_km),
        s(g.depth_m), s(g.wind_speed), s(g.current_speed), s(g.ice_conc_nowcast),
    )


def _cache_key(w: Dict[str, float], draft: float, horizon_h: float, fingerprint: tuple) -> tuple:
    return (tuple(sorted(w.items())), round(float(draft), 3), float(horizon_h), fingerprint)


class RiskService:
    def __init__(self):
        self.grid = global_grid
        self.settings = get_settings()

    def generate_risk_map(self, weights: Optional[Dict[str, float]] = None,
                          vessel_draft_m: Optional[float] = None,
                          forecast_horizon_hours: Optional[float] = None) -> Dict[str, Any]:
        """Compute composite risk on the analysis grid from real loaded data.

        Assumes pipeline.ensure_loaded() has already been called (route_service does this).
        """
        from app.core.pipeline import ensure_loaded
        state = ensure_loaded()

        g = self.grid
        s = self.settings

        w = weights or {
            "ice": s.RISK_WEIGHT_ICE,
            "iceberg": s.RISK_WEIGHT_ICEBERG,
            "weather": s.RISK_WEIGHT_WEATHER,
            "bathymetry": s.RISK_WEIGHT_BATHYMETRY,
            "current": s.RISK_WEIGHT_CURRENT,
        }
        # Fill in any component missing from a caller-supplied partial dict.
        for k, default in (
            ("ice", s.RISK_WEIGHT_ICE), ("iceberg", s.RISK_WEIGHT_ICEBERG),
            ("weather", s.RISK_WEIGHT_WEATHER), ("bathymetry", s.RISK_WEIGHT_BATHYMETRY),
            ("current", s.RISK_WEIGHT_CURRENT),
        ):
            w.setdefault(k, default)

        draft = vessel_draft_m or s.DEFAULT_VESSEL_DRAFT_M
        horizon_h = forecast_horizon_hours or g.predicted_iceberg_horizon_h or s.SEA_ICE_NOWCAST_RISK_HORIZON_H

        key = _cache_key(w, draft, horizon_h, _data_fingerprint(g))
        cached = _risk_cache.get(key)
        if cached is not None and cached["grid_shape"] == g.grid_shape:
            g.risk_grid = cached["risk_grid"]
            g.risk_components = cached["risk_components"]
            resp = dict(cached["response"])
            resp["cached"] = True
            resp["generated_at"] = datetime.now(timezone.utc).isoformat()
            return resp

        warnings: List[str] = []

        # --- Sea ice risk: current AMSR2 concentration, blended with nowcast ---
        ice_now = np.nan_to_num(g.ice_conc, nan=0.0)
        ice_risk_now = np.clip(ice_now, 0, 100)
        nowcast_info = state.get("nowcast") or {}
        if nowcast_info.get("available") and np.isfinite(g.ice_conc_nowcast).any():
            ice_future = np.where(np.isfinite(g.ice_conc_nowcast), g.ice_conc_nowcast, ice_now)
            ice_risk_future = np.clip(ice_future, 0, 100)
            # Route risk should reflect the worse of "ice now" and "ice by the
            # time a vessel could be there" — not average them away.
            ice_risk = np.maximum(ice_risk_now, ice_risk_future)
        else:
            ice_risk = ice_risk_now
            warnings.append(
                f"Sea-ice nowcast unavailable ({nowcast_info.get('reason', 'not computed')}); "
                "ice risk uses current AMSR2 concentration only."
            )

        # --- Iceberg proximity risk: current (confirmed/candidate) positions ---
        dist = np.nan_to_num(g.iceberg_dist_km, nan=9999.0)
        exclusion_km = s.ICEBERG_EXCLUSION_ZONE_NM * 1.852
        berg_risk_current = np.clip(100.0 * (1.0 - dist / (exclusion_km * 10.0)), 0, 100)
        berg_risk_current[dist < exclusion_km] = 100.0

        # --- Iceberg proximity risk: LSTM-predicted future positions ---
        pred_fields = (state.get("predicted_iceberg") or {}).get("fields_by_horizon") or {}
        pred_field, actual_horizon, pred_warning = None, None, None
        if not pred_fields:
            pred_warning = "No predicted iceberg trajectory data available."
        elif horizon_h in pred_fields:
            pred_field, actual_horizon = pred_fields[horizon_h], horizon_h
        else:
            actual_horizon = min(pred_fields.keys(), key=lambda h: abs(h - horizon_h))
            pred_field = pred_fields[actual_horizon]
            pred_warning = (
                f"Predicted-iceberg forecast horizon {horizon_h}h not computed "
                f"(supported: {sorted(pred_fields.keys())}h) — using nearest available horizon {actual_horizon}h."
            )
        if pred_warning:
            warnings.append(pred_warning)
        if pred_field is not None:
            pdist = np.nan_to_num(pred_field, nan=9999.0)
            berg_risk_predicted = np.clip(100.0 * (1.0 - pdist / (exclusion_km * 10.0)), 0, 100)
            berg_risk_predicted[pdist < exclusion_km] = 100.0
            # Predictions are uncertain (not guaranteed future locations —
            # Phase 3): discount their contribution instead of letting a
            # forecast position exclude a cell as hard as a confirmed one.
            predicted_confidence_discount = 0.75
            g.predicted_iceberg_dist_km = pred_field
            g.predicted_iceberg_horizon_h = actual_horizon
            pred_iceberg_meta = state.get("predicted_iceberg") or {}
            day_key = {24: "1d", 72: "3d", 168: "7d"}.get(actual_horizon)
            metrics = pred_iceberg_meta.get("metrics") or {}
            g.predicted_iceberg_uncertainty_km = (
                metrics.get("ADE_km", {}).get(day_key, {}).get("lstm") if day_key else None
            )
        else:
            berg_risk_predicted = np.zeros(g.grid_shape)
            predicted_confidence_discount = 0.0
            warnings.append("No LSTM-predicted iceberg positions available for this risk map.")

        berg_risk = np.maximum(berg_risk_current, berg_risk_predicted * predicted_confidence_discount)

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

        # --- Ocean current risk: from real GLORYS current speed (Part 2) ---
        if np.isfinite(g.current_speed).any():
            cs = np.nan_to_num(g.current_speed, nan=0.0)
            current_risk = np.clip(cs / max(s.CURRENT_RISK_REFERENCE_MS, 1e-6) * 100.0, 0, 100)
        else:
            current_risk = np.zeros(g.grid_shape)
            warnings.append("GLORYS current data unavailable for requested period; current risk defaulted to 0.")

        # --- Composite (each component pre-weighted for exact explainability) ---
        components = {
            "sea_ice": w["ice"] * ice_risk,
            "iceberg_current": np.clip(w["iceberg"] * berg_risk_current, 0, 100),
            "iceberg_predicted": np.clip(w["iceberg"] * berg_risk_predicted * predicted_confidence_discount
                                  - w["iceberg"] * np.minimum(berg_risk_current, berg_risk_predicted * predicted_confidence_discount), 0, 100),
            "weather": w["weather"] * wx_risk,
            "bathymetry": w["bathymetry"] * bathy_risk,
            "current": w["current"] * current_risk,
        }
        # iceberg_predicted above is defined as its marginal contribution over
        # iceberg_current (since berg_risk = max(current, predicted*disc)) so
        # the six components sum to exactly risk_grid without double-counting.
        total = sum(components.values())
        total = np.clip(total, 0, 100)
        g.risk_grid = total
        g.risk_components = components

        field_stats("composite_risk", total)

        finite = total[np.isfinite(total)]
        risk_range = {
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
        }

        response = {
            "resolution_km": g.resolution_km,
            "bounds": g.bounds_4326(),
            "crs": g.crs,
            "api_crs": "EPSG:4326",
            "grid_shape": list(g.grid_shape),
            "risk_range": risk_range,
            "forecast_horizon_hours": actual_horizon if pred_field is not None else None,
            "overlay": {
                "url": "/api/overlays/risk.png",
                "bounds": [[-85.0, -180.0], [85.0, 180.0]],
                "format": "png",
            },
            "provenance": {
                "source": (
                    "Dynamic Risk Engine — real AMSR2 (+ optical-flow nowcast) + GEBCO + "
                    "ERA5 + GLORYS + BYU/SAR iceberg data + LSTM iceberg trajectory prediction"
                ),
                "components": [
                    "sea_ice: AMSR2 concentration, blended with optical-flow nowcast",
                    "iceberg_current: distance to nearest BYU (confirmed) / S1_CFAR (candidate) position",
                    "iceberg_predicted: distance to nearest LSTM-predicted future position (uncertain forecast)",
                    "weather: ERA5 wind speed",
                    "bathymetry: GEBCO depth vs vessel draft",
                    "current: GLORYS surface current speed",
                ],
                "weights": w,
                "predicted_iceberg_confidence_discount": predicted_confidence_discount,
            },
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }

        _risk_cache[key] = {
            "risk_grid": total.copy(),
            "risk_components": {k: v.copy() for k, v in components.items()},
            "response": response,
            "grid_shape": g.grid_shape,
        }
        return response

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
