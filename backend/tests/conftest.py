"""Shared pytest fixtures.

Real IAVNS datasets (~1.8 GB of NetCDF/CSV/SAR files) are not available in
CI/test environments, and tests must verify actual routing/risk *behaviour*,
not just that files can be read. So instead of mocking away the pipeline,
we populate the real `global_grid` singleton with small, deterministic
synthetic fields (ice, depth, wind, currents) that exercise the same code
paths (`RiskService.generate_risk_map`, `route_service.generate_route`,
`_blocked`, A*) that real data would.

`ensure_loaded` is monkeypatched to a no-op in every module that imported it
directly (it's imported at module scope in a few places), so no attempt is
made to read files from disk or validate IAVNS_DATA_DIR during these tests.
"""
from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def grid():
    """The shared analysis grid, for inspecting shapes/bounds in tests."""
    from app.core.grid import global_grid
    return global_grid


@pytest.fixture
def synthetic_ocean(monkeypatch, grid):
    """Populate global_grid with benign synthetic data: open water, no ice,
    deep, calm. Individual tests can further mutate specific cells.
    """
    shape = grid.grid_shape
    grid.ice_conc = np.zeros(shape)
    grid.depth_m = np.full(shape, 500.0)
    grid.elevation_m = -grid.depth_m
    grid.land = ~grid.valid  # only genuinely out-of-AOI cells are "land"
    grid.uo = np.zeros(shape)
    grid.vo = np.zeros(shape)
    grid.u10 = np.full(shape, 2.0)
    grid.v10 = np.full(shape, 0.0)
    grid.wind_speed = np.sqrt(grid.u10 ** 2 + grid.v10 ** 2)
    grid.t2m = np.full(shape, 260.0)
    grid.msl = np.full(shape, 101000.0)
    grid.iceberg_dist_km = np.full(shape, 9999.0)
    grid.risk_grid = np.full(shape, np.nan)
    grid.current_speed = np.zeros(shape)
    grid.predicted_iceberg_dist_km = np.full(shape, np.nan)
    grid.predicted_iceberg_horizon_h = None
    grid.predicted_iceberg_uncertainty_km = None
    grid.ice_conc_nowcast = np.full(shape, np.nan)
    grid.risk_components = {}

    def _noop_ensure_loaded(include_sar: bool = True):
        return {"loaded": True}

    import app.core.pipeline as pipeline
    monkeypatch.setattr(pipeline, "ensure_loaded", _noop_ensure_loaded)

    import app.services.route_service as route_service
    monkeypatch.setattr(route_service, "ensure_loaded", _noop_ensure_loaded)

    import app.api.endpoints as endpoints
    monkeypatch.setattr(endpoints, "ensure_loaded", _noop_ensure_loaded)

    import app.services.risk_service as risk_service
    risk_service._risk_cache.clear()

    return grid


@pytest.fixture
def od_points(synthetic_ocean, grid):
    """A known-valid origin/destination pair (as lat/lon dicts) plus their
    resolved grid indices, on the synthetic open-water grid.
    """
    origin = {"lat": -65.0, "lon": -60.0}
    dest = {"lat": -64.0, "lon": -55.0}
    oi = grid.latlon_to_indices(origin["lat"], origin["lon"])
    di = grid.latlon_to_indices(dest["lat"], dest["lon"])
    assert oi != (None, None) and di != (None, None), "fixture points must be valid grid cells"
    return {"origin": origin, "destination": dest, "origin_idx": oi, "dest_idx": di}


@pytest.fixture
def synthetic_ocean_with_predictions(monkeypatch, synthetic_ocean, grid):
    """Extends `synthetic_ocean` with fake pipeline state for the Part 2
    ML-integration features (predicted iceberg positions, sea-ice nowcast),
    since the real LSTM/optical-flow pipeline needs the real ~1.8GB dataset
    that isn't available in CI. This still exercises the real RiskService /
    route_service code paths that *consume* that state.
    """
    shape = grid.grid_shape
    # A predicted iceberg placed on the straight line between the fixed
    # od_points test coordinates (-65,-60) -> (-64,-55), so route tests
    # that use `od_points` actually transit near it.
    mid_idx = grid.latlon_to_indices(-64.5, -57.5)
    if mid_idx == (None, None):
        mid_idx = (shape[0] // 2, shape[1] // 2)
    mid_i, mid_j = mid_idx
    # Real-ish smooth distance field (km) from the forecast berg position to
    # every grid cell, rather than a single isolated hazardous pixel — a
    # lone cell is trivially routed around, which is valid but makes it hard
    # to exercise the "route actually transits forecast risk" path. This
    # mirrors what pipeline._distance_field produces for one real position.
    R_km = 6371.0
    lat0, lon0 = float(grid.lats[mid_i, mid_j]), float(grid.lons[mid_i, mid_j])
    dlat = np.radians(grid.lats - lat0)
    dlon = np.radians(grid.lons - lon0)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat0)) * np.cos(np.radians(grid.lats)) * np.sin(dlon / 2) ** 2)
    pred_dist = 2 * R_km * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    grid.predicted_iceberg_dist_km = pred_dist
    grid.predicted_iceberg_horizon_h = 24
    grid.ice_conc_nowcast = np.zeros(shape)

    fake_state = {
        "loaded": True,
        "predicted_iceberg": {
            "fields_by_horizon": {24: pred_dist, 72: pred_dist, 168: pred_dist},
            "positions_by_horizon": {24: [(float(grid.lats[mid_i, mid_j]), float(grid.lons[mid_i, mid_j]), "TEST01")]},
            "n_tracks_used": 1,
            "n_tracks_total": 1,
            "model_status": "LSTM",
            "metrics": {"ADE_km": {"1d": {"lstm": 12.3}, "3d": {"lstm": 30.1}, "7d": {"lstm": 55.0}}},
            "horizons_h": (24, 72, 168),
            "note": "synthetic test fixture",
        },
        "nowcast": {
            "available": True, "horizon_h": 24.0, "model_type": "OPTICAL_FLOW_ADVECTION",
            "confidence": 0.8, "metrics": {"MAE_fraction_backtest": 0.05},
            "note": "synthetic test fixture",
        },
    }

    def _fake_ensure_loaded(include_sar: bool = True):
        return fake_state

    import app.core.pipeline as pipeline
    monkeypatch.setattr(pipeline, "ensure_loaded", _fake_ensure_loaded)
    import app.services.route_service as route_service
    monkeypatch.setattr(route_service, "ensure_loaded", _fake_ensure_loaded)
    import app.api.endpoints as endpoints
    monkeypatch.setattr(endpoints, "ensure_loaded", _fake_ensure_loaded)

    import app.services.risk_service as risk_service
    risk_service._risk_cache.clear()

    return grid


@pytest.fixture
def client(synthetic_ocean):
    """FastAPI TestClient with the synthetic ocean grid wired in."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
