"""Phase 4/5/12: routing modes actually behave differently, custom weights
are honored, and hard constraints (depth, ice) genuinely block cells.
"""
import numpy as np

from app.schemas.route import Point, RouteOptimizeRequest, VesselConfig
from app.services.route_service import generate_route, RouteService


def test_fastest_safest_balanced_all_reach_goal_on_open_water(od_points):
    for mode in ("FASTEST", "SAFEST", "BALANCED"):
        r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), mode)
        assert r["fallback"] is False, f"{mode} should reach goal on open water: {r.get('fallback_reason')}"
        assert r["distance_nm"] > 0
        assert r["mode"] == mode


def test_safest_route_has_lower_or_equal_risk_than_fastest(od_points, grid):
    # Carve a lower-risk (0% ice) corridor and a higher-risk (heavy ice) direct
    # strip between origin and destination so FASTEST (which barely weighs
    # risk) and SAFEST (which weighs it heavily) can meaningfully differ.
    oi, di = od_points["origin_idx"], od_points["dest_idx"]
    i0, i1 = sorted([oi[0], di[0]])
    j0, j1 = sorted([oi[1], di[1]])
    grid.ice_conc[max(0, i0 - 2):i1 + 3, j0:j1 + 1] = 70.0  # heavy ice across the direct band

    fastest = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    safest = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "SAFEST")
    assert not fastest["fallback"] and not safest["fallback"]
    assert safest["risk_score"] <= fastest["risk_score"] + 1e-6


def test_custom_mode_weights_are_used_and_returned(od_points):
    req = RouteOptimizeRequest(
        origin=Point(**od_points["origin"]),
        destination=Point(**od_points["destination"]),
        mode="CUSTOM",
        distance_weight=2.0,
        safety_weight=0.9,
        fuel_weight=0.1,
        current_weight=0.0,
    )
    result = RouteService().optimize_route(req)
    modes = [r["mode"] for r in result["routes"]]
    assert "CUSTOM" in modes
    custom = next(r for r in result["routes"] if r["mode"] == "CUSTOM")
    assert custom["weights"]["distance"] == 2.0
    assert custom["weights"]["safety"] == 0.9 * 10.0  # WEIGHT_SCALE["safety"]


def test_default_optimize_route_returns_three_presets(od_points):
    req = RouteOptimizeRequest(origin=Point(**od_points["origin"]), destination=Point(**od_points["destination"]))
    result = RouteService().optimize_route(req)
    modes = sorted(r["mode"] for r in result["routes"])
    assert modes == ["BALANCED", "FASTEST", "SAFEST"]


def test_shallow_water_blocks_start_cell(od_points, grid):
    oi = od_points["origin_idx"]
    grid.depth_m[oi] = 3.0  # far shallower than default draft(8m)+margin(10m)
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    assert r["fallback"] is True
    assert "depth" in r["fallback_reason"].lower() or "Insufficient depth" in r["explanation_text"]


def test_high_ice_blocks_start_cell_for_non_icebreaker(od_points, grid):
    oi = od_points["origin_idx"]
    grid.ice_conc[oi] = 95.0  # above MAX_ICE_CONCENTRATION default (80%)
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    assert r["fallback"] is True
    assert "ice" in r["fallback_reason"].lower()


def test_dedicated_icebreaker_not_blocked_by_high_ice(od_points, grid):
    oi = od_points["origin_idx"]
    grid.ice_conc[oi] = 95.0
    vc = VesselConfig(dedicated_icebreaker=True, draft_m=8.0, max_speed_knots=12.0)
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST", vc)
    assert r["fallback"] is False


def test_invalid_coordinates_rejected_by_schema():
    import pydantic
    try:
        Point(lat=999, lon=0)
        assert False, "should have raised a validation error"
    except pydantic.ValidationError:
        pass


def test_invalid_vessel_draft_rejected_by_schema():
    import pydantic
    try:
        VesselConfig(draft_m=-5.0)
        assert False, "negative draft should be rejected"
    except pydantic.ValidationError:
        pass


def test_route_response_includes_full_metadata(od_points):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "BALANCED")
    for key in (
        "distance_nm", "estimated_time_hours", "fuel_tonnes", "risk_score",
        "route_score", "weights", "warnings", "data_availability",
        "vessel_parameters", "fuel_model",
    ):
        assert key in r, f"missing expected field: {key}"
    assert r["fuel_model"] == "relative_estimate"
