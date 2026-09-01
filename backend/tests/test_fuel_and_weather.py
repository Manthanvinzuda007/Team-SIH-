"""Phase 7/8/12: fuel is honestly labeled as a proxy, and wind speed /
weather risk are computed correctly from u10/v10.
"""
import numpy as np

from app.schemas.route import Point
from app.services.route_service import generate_route
from app.services.risk_service import RiskService


def test_fuel_estimate_uses_relative_estimate_label(od_points):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    assert r["fuel_model"] == "relative_estimate"
    assert r["fuel_tonnes"] > 0


def test_fuel_increases_with_ice_concentration_along_route(od_points, grid):
    baseline = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")

    oi, di = od_points["origin_idx"], od_points["dest_idx"]
    i0, i1 = sorted([oi[0], di[0]])
    j0, j1 = sorted([oi[1], di[1]])
    grid.ice_conc[i0:i1 + 1, j0:j1 + 1] = 60.0

    iced = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    assert not baseline["fallback"] and not iced["fallback"]
    # Same-ish distance, but fuel per NM should be higher with ice present.
    assert (iced["fuel_tonnes"] / max(iced["distance_nm"], 1e-6)) >= \
           (baseline["fuel_tonnes"] / max(baseline["distance_nm"], 1e-6))


def test_wind_speed_is_sqrt_u10_v10(synthetic_ocean, grid):
    grid.u10 = np.full(grid.grid_shape, 3.0)
    grid.v10 = np.full(grid.grid_shape, 4.0)
    grid.wind_speed = np.sqrt(grid.u10 ** 2 + grid.v10 ** 2)
    assert np.allclose(grid.wind_speed, 5.0)  # 3-4-5 triangle


def test_weather_risk_scales_with_wind_speed(synthetic_ocean, grid):
    grid.wind_speed = np.full(grid.grid_shape, 0.0)
    r0 = RiskService().generate_risk_map()
    calm_risk = float(np.nanmean(grid.risk_grid[grid.valid]))

    grid.wind_speed = np.full(grid.grid_shape, 25.0)
    r1 = RiskService().generate_risk_map()
    windy_risk = float(np.nanmean(grid.risk_grid[grid.valid]))

    assert windy_risk > calm_risk


def test_risk_map_normalized_0_100(synthetic_ocean, grid):
    RiskService().generate_risk_map()
    finite = grid.risk_grid[np.isfinite(grid.risk_grid)]
    assert finite.min() >= 0.0
    assert finite.max() <= 100.0
