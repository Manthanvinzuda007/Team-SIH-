"""A* router on the shared analysis grid.

Vessel safety logic:
  - dedicated_icebreaker=True  → no ice concentration hard limit
  - icebreaking_capable=True   → relaxed ice limit (MAX_ICE * 1.4)
  - otherwise                  → MAX_ICE_CONCENTRATION hard limit applies

Hard exclusions (always):
  - land / depth < vessel_draft + MIN_DEPTH_MARGIN_M (bathymetry)

Soft penalties are added for all vessels but do not block.
"""
from __future__ import annotations

import heapq
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.geo import haversine_nm
from app.core.grid import global_grid
from app.core.pipeline import ensure_loaded
from app.schemas.route import RouteOptimizeRequest, VesselConfig

logger = logging.getLogger("polaris.route")


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


def _blocked(i: int, j: int, vc: Optional[VesselConfig]) -> bool:
    s = get_settings()
    g = global_grid
    if not g.valid[i, j]:
        return True
    if g.land[i, j]:
        return True
    depth = g.depth_m[i, j]
    draft = vc.draft_m if vc else s.DEFAULT_VESSEL_DRAFT_M
    need = draft + s.MIN_DEPTH_MARGIN_M
    if depth == depth and 0 < depth < need:   # nan-safe
        return True
    ice_lim = _ice_limit(vc)
    if ice_lim < 100.0:
        ice = g.ice_conc[i, j]
        if ice == ice and ice > ice_lim:
            return True
    return False


def generate_route(
    origin, dest, mode: str, vc: Optional[VesselConfig] = None
) -> Dict:
    """Run A* from origin to dest with mode-specific weights. Returns route dict."""
    ensure_loaded()
    # compute risk map into global_grid.risk_grid
    from app.services.risk_service import RiskService
    RiskService().generate_risk_map(
        vessel_draft_m=vc.draft_m if vc else None
    )

    s = get_settings()
    g = global_grid
    lat1, lon1 = float(origin.lat), float(origin.lon)
    lat2, lon2 = float(dest.lat), float(dest.lon)
    draft = vc.draft_m if vc else s.DEFAULT_VESSEL_DRAFT_M
    base_knots = vc.max_speed_knots if vc else 12.0

    start_idx = g.latlon_to_indices(lat1, lon1)
    goal_idx = g.latlon_to_indices(lat2, lon2)

    if start_idx == (None, None) or goal_idx == (None, None):
        return _fallback(lat1, lon1, lat2, lon2, mode, base_knots,
                         "Origin or destination outside analysis AOI")

    if _blocked(*start_idx, vc) or _blocked(*goal_idx, vc):
        return _fallback(lat1, lon1, lat2, lon2, mode, base_knots,
                         "Start/goal cell blocked by depth or ice constraint")

    if mode == "FASTEST":
        w_dist, w_risk = 1.0, 0.3
    elif mode == "SAFEST":
        w_dist, w_risk = 0.6, 8.0
    else:  # BALANCED
        w_dist, w_risk = 1.0, 2.0

    open_set: List[Tuple[float, Tuple[int, int]]] = []
    heapq.heappush(open_set, (0.0, start_idx))
    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start_idx: 0.0}
    visited: set = set()

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
            return _reconstruct(came_from, current, mode, w_dist, w_risk, draft, vc, base_knots)

        for di, dj in [(0,1),(1,0),(0,-1),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
            nb = (current[0] + di, current[1] + dj)
            if not (0 <= nb[0] < g.nlat and 0 <= nb[1] < g.nlon):
                continue
            if _blocked(*nb, vc):
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
            # diagonal step cost ×√2 already encoded in step_nm
            step_cost = (w_dist * step_nm) + (w_risk * float(risk_n) * step_nm * 0.01)
            tent = g_score[current] + step_cost
            if nb not in g_score or tent < g_score[nb]:
                came_from[nb] = current
                g_score[nb] = tent
                heapq.heappush(open_set, (tent + h(nb), nb))

    return _fallback(lat1, lon1, lat2, lon2, mode, base_knots,
                     f"A* exhausted after {iters} iterations (grid may be fully blocked)")


def _reconstruct(
    came_from: Dict, current: Tuple[int, int], mode: str,
    w_dist: float, w_risk: float, draft: float,
    vc: Optional[VesselConfig], base_knots: float
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
        ice = g.ice_conc[idx]
        if ice == ice and ice > 15:
            ice_encounters += 1

    avg_risk = total_risk_w / total_nm if total_nm > 0 else 0.0

    # Effective speed: reduce by ice and risk (decision-support proxy, not hydrodynamic)
    ice_penalty = min(0.4, avg_risk / 250.0)   # up to 40% speed reduction
    eff_knots = base_knots * (1.0 - ice_penalty)
    eta_h = total_nm / eff_knots if eff_knots > 0 else 0.0

    # Fuel proxy: 0.13 t/NM base, +ice penalty
    fuel = total_nm * 0.13 * (1.0 + ice_penalty)

    return {
        "mode": mode,
        "path_points": pts,
        "distance_nm": round(total_nm, 1),
        "estimated_time_hours": round(eta_h, 1),
        "base_speed_knots": round(base_knots, 1),
        "effective_speed_knots": round(eff_knots, 1),
        "fuel_tonnes": round(fuel, 1),
        "fuel_model": "distance_proxy_0.13t_per_nm × (1 + ice_penalty)",
        "safety_score": round(max(0.0, 100.0 - avg_risk), 2),
        "risk_score": round(avg_risk, 2),
        "ice_encounters": ice_encounters,
        "explanation_text": "",
        "weights": {"distance": w_dist, "risk": w_risk},
        "constraints": {
            "draft_m": draft,
            "dedicated_icebreaker": vc.dedicated_icebreaker if vc else False,
            "icebreaking_capable": vc.icebreaking_capable if vc else False,
            "ice_class": vc.ice_class if vc else None,
            "ice_limit_pct": _ice_limit(vc),
        },
        "fallback": False,
        "fallback_reason": None,
        "computed_at": datetime.utcnow().isoformat() + "Z",
        "data_valid_time": "2026-08-08 (AMSR2 last frame)",
        "n_cells": len(path),
    }


def _fallback(lat1, lon1, lat2, lon2, mode, base_knots, reason) -> Dict:
    nm = distance_nm(lat1, lon1, lat2, lon2)
    eta_h = nm / base_knots if base_knots > 0 else 0.0
    logger.warning("Route fallback [%s]: %s", mode, reason)
    return {
        "mode": mode,
        "path_points": [{"lat": lat1, "lon": lon1}, {"lat": lat2, "lon": lon2}],
        "distance_nm": round(nm, 1),
        "estimated_time_hours": round(eta_h, 1),
        "base_speed_knots": round(base_knots, 1),
        "effective_speed_knots": round(base_knots, 1),
        "fuel_tonnes": round(nm * 0.13, 1),
        "fuel_model": "distance_proxy_0.13t_per_nm",
        "safety_score": None,
        "risk_score": None,
        "ice_encounters": 0,
        "explanation_text": (
            f"[FALLBACK] Direct geodesic — A* could not find a grid path. "
            f"Reason: {reason}. Not a risk-optimized route."
        ),
        "weights": {},
        "constraints": {},
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
        r["explanation_text"] = " ".join(bits)
    return routes


class RouteService:
    def optimize_route(self, request: RouteOptimizeRequest) -> Dict:
        vc = request.vessel_config
        modes = ["FASTEST", "SAFEST", "BALANCED"]
        routes = [generate_route(request.origin, request.destination, m, vc) for m in modes]
        _explain(routes)
        return {
            "routes": routes,
            "vessel_config": vc.model_dump() if vc else None,
            "computed_at": datetime.utcnow().isoformat() + "Z",
        }
