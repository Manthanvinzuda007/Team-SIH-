"""A* router on the shared analysis grid.

Vessel safety logic:
  - dedicated_icebreaker=True  → no ice concentration hard limit
  - icebreaking_capable=True   → relaxed ice limit (MAX_ICE * 1.4)
  - otherwise                  → MAX_ICE_CONCENTRATION hard limit applies

Hard exclusions (always):
  - land / depth < vessel_draft + MIN_DEPTH_MARGIN_M (bathymetry)

Cost function
-------------
Adapted (not a literal copy) from the brief's conceptual formula. Per A* edge
(current cell -> neighbour cell), all cost components are normalized to be
roughly comparable before weighting so that turning a weight up/down has a
predictable effect regardless of route length or grid resolution:

    step_cost =
        distance_weight * distance_cost          # step_nm, natural unit (nm)
      + safety_weight   * risk_cost   * step_nm   # risk_cost in [0,1]
      + fuel_weight     * fuel_cost   * step_nm   # fuel_cost in [1,~1.4]
      + current_weight  * current_cost * step_nm  # current_cost in [-1,~1.5]
      + ice_penalty     * step_nm                 # always-on, small, [0,0.05]
      + bathymetry_penalty * step_nm              # always-on, [0,0.3]

`ice_penalty` and `bathymetry_penalty` are always applied (not user-weighted)
because they represent physical caution near hard constraints, not a
preference the operator should be able to switch off — the hard block
(`_blocked`) already excludes genuinely unsafe cells; these soft terms bias
A* away from cells *near* that boundary before it is reached.

FASTEST/SAFEST/BALANCED use fixed internal weight presets (BALANCED/SAFEST
line up with the original single distance+risk formula plus new fuel/current
terms at modest weight). CUSTOM uses the caller's 0-1 weights, rescaled by
WEIGHT_SCALE so a CUSTOM request with default weights behaves similarly to
BALANCED.
"""
from __future__ import annotations

import heapq
import logging
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.geo import haversine_nm
from app.core.grid import global_grid
from app.core.pipeline import ensure_loaded
from app.schemas.route import RouteOptimizeRequest, VesselConfig

logger = logging.getLogger("polaris.route")

# Rescale CUSTOM-mode 0-1 weights into the same magnitude range used by the
# FASTEST/SAFEST/BALANCED presets below. Design choice, documented here so
# it's easy to retune.
WEIGHT_SCALE = {"safety": 10.0, "fuel": 3.0, "current": 3.0}

# Ice-class soft risk tolerance: how much of the ice-concentration
# contribution to composite risk a vessel of this class "discounts" when
# A* scores candidate cells. 1.0 = no discount (feels full ice risk),
# lower = more ice-hardened. This does NOT relax the hard ice-concentration
# block (`_ice_limit`), which is governed solely by icebreaking_capable /
# dedicated_icebreaker. This is a routing-preference heuristic, not a
# regulatory or structural-strength claim.
ICE_CLASS_TOLERANCE = {
    "PC1": 0.55, "PC2": 0.60, "PC3": 0.65, "PC4": 0.70, "PC5": 0.75,
    "PC6": 0.85, "PC7": 0.90,
    "IA_SUPER": 0.75, "IA": 0.85, "IB": 0.92, "IC": 0.97,
}


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_nm(lat1, lon1, lat2, lon2)


def _ice_limit(vc: Optional[VesselConfig]) -> float:
    """Return effective ice concentration hard limit (0-100) for this vessel."""
    s = get_settings()
    if vc is None:
        return s.MAX_ICE_CONCENTRATION
    if vc.dedicated_icebreaker:
        return 100.0   # no ice limit for dedicated icebreakers
    if vc.icebreaking_capable:
        return min(100.0, s.MAX_ICE_CONCENTRATION * 1.4)
    return s.MAX_ICE_CONCENTRATION


def _blocked(i: int, j: int, vc: Optional[VesselConfig]) -> Tuple[bool, Optional[str]]:
    """Return (blocked, reason). Reason is populated only when blocked."""
    s = get_settings()
    g = global_grid
    if not g.valid[i, j]:
        return True, "Outside analysis AOI"
    if g.land[i, j]:
        return True, "Land"
    depth = g.depth_m[i, j]
    draft = vc.draft_m if vc else s.DEFAULT_VESSEL_DRAFT_M
    need = draft + s.MIN_DEPTH_MARGIN_M
    if depth == depth and 0 < depth < need:   # nan-safe
        return True, f"Insufficient depth for selected vessel (depth {depth:.0f}m < required {need:.0f}m)"
    ice_lim = _ice_limit(vc)
    if ice_lim < 100.0:
        ice = g.ice_conc[i, j]
        if ice == ice and ice > ice_lim:
            return True, f"Ice concentration {ice:.0f}% exceeds vessel limit {ice_lim:.0f}%"
    return False, None


def _ice_class_tolerance(vc: Optional[VesselConfig]) -> float:
    if vc is None or not vc.ice_class:
        return 1.0
    return ICE_CLASS_TOLERANCE.get(vc.ice_class.upper(), 1.0)


def _weights_for_mode(mode: str, request: Optional[RouteOptimizeRequest]) -> Dict[str, float]:
    """Resolve the (distance, safety, fuel, current) weight tuple for a mode."""
    if mode == "FASTEST":
        return {"distance": 1.0, "safety": 0.3, "fuel": 0.0, "current": 0.0}
    if mode == "SAFEST":
        return {"distance": 0.6, "safety": 8.0, "fuel": 0.0, "current": 0.0}
    if mode == "BALANCED":
        return {"distance": 1.0, "safety": 2.0, "fuel": 0.3, "current": 0.2}
    if mode == "CUSTOM":
        if request is None:
            return {"distance": 1.0, "safety": 5.0, "fuel": 0.9, "current": 0.6}
        return {
            "distance": float(request.distance_weight),
            "safety": float(request.safety_weight) * WEIGHT_SCALE["safety"],
            "fuel": float(request.fuel_weight) * WEIGHT_SCALE["fuel"],
            "current": float(request.current_weight) * WEIGHT_SCALE["current"],
        }
    raise ValueError(f"Unknown routing mode: {mode}")


def _current_cost(lat_c, lon_c, lat_n, lon_n, uo, vo) -> Tuple[float, bool]:
    """Along-track current cost in ~[-1, 1.5]. Positive = current opposes travel.

    Returns (cost, data_missing). Uses a flat-earth local tangent approximation
    (adequate for single grid-cell steps ~10 km) — not a full great-circle
    bearing solve, which would be overkill at this scale.
    """
    if not (uo == uo and vo == vo):  # nan check
        return 0.0, True
    dlat = lat_n - lat_c
    dlon = (lon_n - lon_c) * math.cos(math.radians((lat_c + lat_n) / 2.0))
    norm = math.hypot(dlat, dlon)
    if norm < 1e-12:
        return 0.0, False
    north, east = dlat / norm, dlon / norm
    along_track = uo * east + vo * north  # m/s, +ve = current assists travel
    s = get_settings()
    ref = max(s.CURRENT_REFERENCE_MS, 1e-6)
    cost = -along_track / ref
    return max(-1.0, min(1.5, cost)), False


def _choose_forecast_horizon(straight_nm: float, base_knots: float) -> float:
    """Bucket a rough straight-line ETA into one of the supported LSTM
    trajectory forecast horizons (24/72/168h), so the predicted-iceberg risk
    layer reflects roughly how far into the future this vessel will actually
    be transiting — not always the same fixed horizon regardless of trip length.
    """
    supported = (24.0, 72.0, 168.0)
    if base_knots <= 0:
        return supported[0]
    rough_eta_h = straight_nm / base_knots
    return min(supported, key=lambda h: abs(h - rough_eta_h))


def _find_nearest_unblocked_cell(idx: Tuple[int, int], vc: Optional[VesselConfig], max_radius: int = 15) -> Optional[Tuple[int, int]]:
    """Find the nearest unblocked cell in expanding concentric rings around idx."""
    g = global_grid
    blocked, _ = _blocked(*idx, vc)
    if not blocked:
        return idx
    i0, j0 = idx
    for r in range(1, max_radius + 1):
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if max(abs(di), abs(dj)) != r:
                    continue
                ni, nj = i0 + di, j0 + dj
                if 0 <= ni < g.nlat and 0 <= nj < g.nlon:
                    b, _ = _blocked(ni, nj, vc)
                    if not b:
                        return (ni, nj)
    return None


def generate_route(
    origin, dest, mode: str, vc: Optional[VesselConfig] = None,
    request: Optional[RouteOptimizeRequest] = None,
) -> Dict:
    """Run A* from origin to dest with mode-specific weights. Returns route dict."""
    ensure_loaded()

    s = get_settings()
    g = global_grid
    lat1, lon1 = float(origin.lat), float(origin.lon)
    lat2, lon2 = float(dest.lat), float(dest.lon)
    draft = vc.draft_m if vc else s.DEFAULT_VESSEL_DRAFT_M
    base_knots = vc.max_speed_knots if vc else 12.0

    # Pick a forecast horizon for the predicted-iceberg risk layer from a
    # rough straight-line ETA, then compute the risk map once for this route.
    straight_nm = distance_nm(lat1, lon1, lat2, lon2)
    forecast_horizon_h = _choose_forecast_horizon(straight_nm, base_knots)
    from app.services.risk_service import RiskService
    risk_response = RiskService().generate_risk_map(
        vessel_draft_m=draft, forecast_horizon_hours=forecast_horizon_h,
    )

    raw_start = g.latlon_to_indices(lat1, lon1)
    raw_goal = g.latlon_to_indices(lat2, lon2)

    if raw_start == (None, None) or raw_goal == (None, None):
        return _fallback(lat1, lon1, lat2, lon2, mode, base_knots,
                         "Origin or destination outside analysis AOI", risk_response)

    start_idx = _find_nearest_unblocked_cell(raw_start, vc) or raw_start
    goal_idx = _find_nearest_unblocked_cell(raw_goal, vc) or raw_goal

    start_blocked, start_reason = _blocked(*start_idx, vc)
    goal_blocked, goal_reason = _blocked(*goal_idx, vc)
    if start_blocked or goal_blocked:
        reason = start_reason if start_blocked else goal_reason
        return _fallback(lat1, lon1, lat2, lon2, mode, base_knots,
                         f"Start/goal cell blocked: {reason}", risk_response)

    weights = _weights_for_mode(mode, request)
    w_dist, w_safety = weights["distance"], weights["safety"]
    w_fuel, w_current = weights["fuel"], weights["current"]
    ice_tolerance = _ice_class_tolerance(vc)
    ice_risk_share = s.RISK_WEIGHT_ICE  # portion of composite risk attributable to ice

    open_set: List[Tuple[float, Tuple[int, int]]] = []
    heapq.heappush(open_set, (0.0, start_idx))
    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start_idx: 0.0}
    visited: set = set()
    current_data_missing_any = False

    def h(idx: Tuple[int, int]) -> float:
        return distance_nm(float(g.lats[idx]), float(g.lons[idx]), lat2, lon2)

    MAX_ITER = 200_000
    iters = 0
    while open_set and iters < MAX_ITER:
        iters += 1
        _, current = heapq.heappop(open_set)
        if current in visited:
            continue
        visited.add(current)
        if current == goal_idx:
            return _reconstruct(
                came_from, current, mode, weights, draft, vc, base_knots,
                current_data_missing_any, request, risk_response,
            )

        for di, dj in [(0,1),(1,0),(0,-1),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
            nb = (current[0] + di, current[1] + dj)
            if not (0 <= nb[0] < g.nlat and 0 <= nb[1] < g.nlon):
                continue
            blocked, _reason = _blocked(*nb, vc)
            if blocked:
                continue
            risk_n = g.risk_grid[nb]
            if not (risk_n == risk_n):   # nan
                continue
            if mode == "SAFEST" and risk_n > 85:
                continue   # hard block for safest mode on very high risk

            lat_c = float(g.lats[current])
            lon_c = float(g.lons[current])
            lat_n = float(g.lats[nb])
            lon_n = float(g.lons[nb])
            step_nm = distance_nm(lat_c, lon_c, lat_n, lon_n)

            # --- vessel ice-class tolerance applied to the ice share of risk ---
            ice_local = g.ice_conc[nb]
            ice_local = float(ice_local) if ice_local == ice_local else 0.0
            ice_component = ice_risk_share * ice_local  # approx ice contribution to risk_n
            vessel_risk_n = float(risk_n) - ice_component * (1.0 - ice_tolerance)
            risk_cost = max(0.0, vessel_risk_n) / 100.0  # normalized [0,1]

            # --- fuel proxy cost: relative burn rate, 1.0 = open water ---
            fuel_cost = 1.0 + min(0.4, (ice_local / 100.0) * 0.4)

            # --- current cost: along-track current vs travel direction ---
            uo_n, vo_n = g.uo[nb], g.vo[nb]
            current_cost, missing = _current_cost(lat_c, lon_c, lat_n, lon_n, uo_n, vo_n)
            if missing:
                current_data_missing_any = True

            # --- always-on soft penalties near hard constraints ---
            ice_penalty = 0.05 * (ice_local / 100.0) ** 2
            depth_n = g.depth_m[nb]
            need = draft + s.MIN_DEPTH_MARGIN_M
            bathy_penalty = 0.0
            if depth_n == depth_n:  # finite (not land)
                caution_band = need * 3.0
                if depth_n < caution_band:
                    frac = max(0.0, min(1.0, (caution_band - depth_n) / max(caution_band - need, 1e-6)))
                    bathy_penalty = 0.3 * frac ** 2

            step_cost = (
                w_dist * step_nm
                + w_safety * risk_cost * step_nm
                + w_fuel * fuel_cost * step_nm
                + w_current * current_cost * step_nm
                + ice_penalty * step_nm
                + bathy_penalty * step_nm
            )

            tent = g_score[current] + step_cost
            if nb not in g_score or tent < g_score[nb]:
                came_from[nb] = current
                g_score[nb] = tent
                heapq.heappush(open_set, (tent + h(nb), nb))

    return _fallback(lat1, lon1, lat2, lon2, mode, base_knots,
                     f"A* exhausted after {iters} iterations (grid may be fully blocked)", risk_response)


def _reconstruct(
    came_from: Dict, current: Tuple[int, int], mode: str,
    weights: Dict[str, float], draft: float,
    vc: Optional[VesselConfig], base_knots: float,
    current_data_missing: bool,
    request: Optional[RouteOptimizeRequest],
    risk_response: Dict,
) -> Dict:
    s = get_settings()
    g = global_grid
    path = []
    node = current
    while node in came_from:
        path.append(node)
        node = came_from[node]
    path.append(node)
    path.reverse()

    pts = []
    total_nm = 0.0
    total_risk_w = 0.0
    seg_risks = []
    ice_encounters = 0
    ice_frac_sum = 0.0
    total_fuel_tonnes = 0.0
    FUEL_BASE_T_PER_NM = 0.13  # design-choice proxy rate, see fuel_model label
    component_names = ("sea_ice", "iceberg_current", "iceberg_predicted", "weather", "bathymetry", "current")
    component_w_sums = {c: 0.0 for c in component_names}
    has_components = bool(g.risk_components)

    for k, idx in enumerate(path):
        la, lo = float(g.lats[idx]), float(g.lons[idx])
        pts.append({"lat": la, "lon": lo})
        if k == 0:
            continue
        prev = path[k - 1]
        nm = distance_nm(float(g.lats[prev]), float(g.lons[prev]), la, lo)
        r = float(g.risk_grid[idx])
        total_nm += nm
        total_risk_w += r * nm
        seg_risks.append(r)
        if has_components:
            for c in component_names:
                v = g.risk_components[c][idx]
                if v == v:  # nan-safe
                    component_w_sums[c] += float(v) * nm
        ice = g.ice_conc[idx]
        ice_val = float(ice) if ice == ice else 0.0
        ice_frac_sum += (ice_val / 100.0) * nm
        if ice_val > 15:
            ice_encounters += 1
        total_fuel_tonnes += nm * FUEL_BASE_T_PER_NM * (1.0 + min(0.4, (ice_val / 100.0) * 0.4))

    avg_risk = total_risk_w / total_nm if total_nm > 0 else 0.0
    avg_ice_frac = ice_frac_sum / total_nm if total_nm > 0 else 0.0

    # Effective speed: reduce by ice/risk (decision-support proxy, not hydrodynamic).
    ice_penalty_speed = min(0.4, avg_risk / 250.0)
    eff_knots = base_knots * (1.0 - ice_penalty_speed)

    # Icebreaking-capable (but not dedicated-icebreaker) vessels take an
    # additional configurable speed penalty when transiting higher ice —
    # they are cleared to enter it, but not at full open-water speed.
    if vc and vc.icebreaking_capable and not vc.dedicated_icebreaker:
        extra = min(0.35, avg_ice_frac * s.ICEBREAKING_SPEED_PENALTY_FACTOR)
        eff_knots *= (1.0 - extra)

    eff_knots = max(eff_knots, 0.5)  # floor to avoid divide-by-near-zero ETAs
    eta_h = total_nm / eff_knots if eff_knots > 0 else 0.0

    safety_score = round(max(0.0, 100.0 - avg_risk), 2)

    # --- Explainable per-route risk breakdown (Part 2 Phase 8) ---
    risk_breakdown = None
    primary_hazard = None
    _HAZARD_LABELS = {
        "sea_ice": "Sea ice concentration",
        "iceberg_current": "Proximity to confirmed/candidate iceberg",
        "iceberg_predicted": "Predicted iceberg proximity",
        "weather": "Weather (wind)",
        "bathymetry": "Shallow water / bathymetry",
        "current": "Ocean current",
    }
    if has_components and total_nm > 0:
        risk_breakdown = {c: round(v / total_nm, 2) for c, v in component_w_sums.items()}
        risk_breakdown["iceberg_total"] = round(
            risk_breakdown["iceberg_current"] + risk_breakdown["iceberg_predicted"], 2
        )
        risk_breakdown["total"] = round(avg_risk, 2)
        top_component = max(
            (c for c in component_names), key=lambda c: risk_breakdown[c]
        )
        if risk_breakdown[top_component] > 0:
            primary_hazard = f"Primary Hazard: {_HAZARD_LABELS[top_component]}"
        else:
            primary_hazard = "Primary Hazard: None (open water, low risk)"

    warnings: List[str] = list(risk_response.get("warnings", []))
    if current_data_missing:
        warnings.append(
            "Ocean-current data unavailable for one or more route cells; "
            "current-aware cost for those segments defaulted to zero "
            "(no current-aware routing was performed there)."
        )
    if vc and vc.icebreaking_capable and not vc.dedicated_icebreaker and avg_ice_frac > 0.15:
        warnings.append(
            "Route transits significant ice concentration; effective speed reduced "
            "by the configured icebreaking efficiency penalty."
        )
    if risk_breakdown and risk_breakdown.get("iceberg_predicted", 0) > 0:
        warnings.append(
            "Route risk includes a forecast-based predicted-iceberg-position "
            "component (LSTM trajectory model). Predicted positions are model "
            "estimates, not guaranteed future locations."
        )

    # Simple, documented comparison score — NOT a certified safety/efficiency
    # rating. Rewards low average risk and penalizes ice encounters lightly.
    route_score = round(max(0.0, 100.0 - avg_risk * 0.6 - ice_encounters * 1.0), 2)

    data_availability = {
        "sea_ice": _finite_any(g.ice_conc),
        "bathymetry": _finite_any(g.depth_m),
        "weather": _finite_any(g.wind_speed),
        "ocean_currents": _finite_any(g.uo) and not current_data_missing,
        "iceberg_proximity": _finite_any(g.iceberg_dist_km),
        "predicted_iceberg_positions": _finite_any(g.predicted_iceberg_dist_km),
        "sea_ice_nowcast": _finite_any(g.ice_conc_nowcast),
    }

    return {
        "mode": mode,
        "path_points": pts,
        "distance_nm": round(total_nm, 1),
        "estimated_time_hours": round(eta_h, 1),
        "base_speed_knots": round(base_knots, 1),
        "effective_speed_knots": round(eff_knots, 1),
        "fuel_tonnes": round(total_fuel_tonnes, 1),
        "fuel_model": "relative_estimate",
        "safety_score": safety_score,
        "risk_score": round(avg_risk, 2),
        "risk_breakdown": risk_breakdown,
        "primary_hazard": primary_hazard,
        "forecast_horizon_hours": risk_response.get("forecast_horizon_hours"),
        "predicted_iceberg_uncertainty_km": g.predicted_iceberg_uncertainty_km,
        "route_score": route_score,
        "ice_encounters": ice_encounters,
        "explanation_text": "",
        "weights": weights,
        "constraints": {
            "draft_m": draft,
            "dedicated_icebreaker": vc.dedicated_icebreaker if vc else False,
            "icebreaking_capable": vc.icebreaking_capable if vc else False,
            "ice_class": vc.ice_class if vc else None,
            "ice_limit_pct": _ice_limit(vc),
            "ice_class_risk_tolerance": _ice_class_tolerance(vc),
        },
        "vessel_parameters": vc.model_dump() if vc else None,
        "warnings": warnings,
        "data_availability": data_availability,
        "fallback": False,
        "fallback_reason": None,
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "data_valid_time": "2026-08-08 (AMSR2 last frame)",
        "n_cells": len(path),
    }


def _finite_any(arr) -> bool:
    import numpy as np
    return bool(np.isfinite(arr).any())


def _fallback(lat1, lon1, lat2, lon2, mode, base_knots, reason, risk_response: Optional[Dict] = None) -> Dict:
    nm = distance_nm(lat1, lon1, lat2, lon2)
    eta_h = nm / base_knots if base_knots > 0 else 0.0
    logger.warning("Route fallback [%s]: %s", mode, reason)
    warnings = [f"Fallback route used: {reason}"]
    if risk_response:
        warnings.extend(risk_response.get("warnings", []))
    return {
        "mode": mode,
        "path_points": [{"lat": lat1, "lon": lon1}, {"lat": lat2, "lon": lon2}],
        "distance_nm": round(nm, 1),
        "estimated_time_hours": round(eta_h, 1),
        "base_speed_knots": round(base_knots, 1),
        "effective_speed_knots": round(base_knots, 1),
        "fuel_tonnes": round(nm * 0.13, 1),
        "fuel_model": "relative_estimate",
        "safety_score": None,
        "risk_score": None,
        "risk_breakdown": None,
        "primary_hazard": None,
        "forecast_horizon_hours": risk_response.get("forecast_horizon_hours") if risk_response else None,
        "predicted_iceberg_uncertainty_km": None,
        "route_score": None,
        "ice_encounters": 0,
        "explanation_text": (
            f"[FALLBACK] Direct geodesic — A* could not find a grid path. "
            f"Reason: {reason}. Not a risk-optimized route."
        ),
        "weights": {},
        "constraints": {},
        "vessel_parameters": None,
        "warnings": warnings,
        "data_availability": {},
        "fallback": True,
        "fallback_reason": reason,
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "data_valid_time": "2026-08-08 (AMSR2 last frame)",
        "n_cells": 2,
    }


def _explain(routes: List[Dict]) -> List[Dict]:
    by = {r["mode"]: r for r in routes}
    f, s, b = by.get("FASTEST"), by.get("SAFEST"), by.get("BALANCED")

    def delta(a, c, key):
        va, vc = a.get(key), c.get(key)
        if va is None or vc is None:
            return None
        return round(float(vc) - float(va), 1)

    for r in routes:
        if r.get("fallback"):
            continue
        mode = r["mode"]
        bits = [
            f"{mode} A* on 10km EPSG:3031 grid: {r['distance_nm']} NM, "
            f"mean risk {r.get('risk_score')}/100, "
            f"ETA {r['estimated_time_hours']}h @ {r.get('effective_speed_knots', r['base_speed_knots'])} kn, "
            f"fuel-proxy {r['fuel_tonnes']}t."
        ]
        if mode == "SAFEST" and f and not f.get("fallback"):
            bits.append(
                f"+{delta(f, r, 'distance_nm')} NM vs FASTEST; "
                f"risk cut by {round(float(f.get('risk_score') or 0) - float(r.get('risk_score') or 0), 1)} pts."
            )
        if mode == "BALANCED" and f and s and not f.get("fallback") and not s.get("fallback"):
            bits.append(
                f"Middle ground: {delta(f, r, 'distance_nm')} NM vs FASTEST, "
                f"{delta(s, r, 'distance_nm')} NM vs SAFEST."
            )
        if mode == "CUSTOM":
            bits.append(
                f"Custom weights: distance={r['weights'].get('distance')}, "
                f"safety={r['weights'].get('safety')}, fuel={r['weights'].get('fuel')}, "
                f"current={r['weights'].get('current')}."
            )
        r["explanation_text"] = " ".join(bits)
    return routes


class RouteService:
    def optimize_route(self, request: RouteOptimizeRequest) -> Dict:
        vc = request.vessel_config
        modes = ["FASTEST", "SAFEST", "BALANCED"]
        if request.mode == "CUSTOM":
            modes.append("CUSTOM")
        routes = [generate_route(request.origin, request.destination, m, vc, request) for m in modes]
        _explain(routes)
        return {
            "routes": routes,
            "vessel_config": vc.model_dump() if vc else None,
            "computed_at": datetime.utcnow().isoformat() + "Z",
        }
