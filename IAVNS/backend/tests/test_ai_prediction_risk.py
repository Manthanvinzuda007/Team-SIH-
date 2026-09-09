"""Part 2 — AI Prediction + Risk Intelligence.

Covers Phase 13 requirements: model loading/status, prediction input
validation, output shape, forecast horizons, missing-data handling,
prediction-to-risk integration, predicted-iceberg route penalty, and
risk-map generation with the new explainable fields.

Real IAVNS datasets aren't available in CI (see conftest.py), so these tests
either (a) exercise the real numpy LSTM / CFAR / optical-flow model classes
directly on small synthetic inputs, or (b) use `synthetic_ocean_with_predictions`
to feed realistic *pipeline-shaped* fake state into the real RiskService /
route_service code paths that consume it.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from app.schemas.route import Point
from app.services.route_service import generate_route
from app.services.risk_service import RiskService


# ── Model-level tests (no pipeline/dataset needed) ─────────────────────────

def _make_track(n=20, start_lat=-65.0, start_lon=-60.0, dlat=0.02, dlon=0.03, day_step=1.0):
    pts = []
    t0 = datetime(2026, 8, 1)
    for i in range(n):
        pts.append({
            "lat": start_lat + i * dlat,
            "lon": start_lon + i * dlon,
            "timestamp": (t0 + timedelta(days=i * day_step)).isoformat(),
        })
    return pts


def test_lstm_or_persistence_predicts_structured_output():
    from app.ml.iceberg_trajectory import IcebergTrajectoryPredictor
    pred = IcebergTrajectoryPredictor()
    pts = _make_track()
    out = pred.predict("TEST_BERG", pts, forecast_hours=[24, 72, 168])
    assert out["model_type"] in ("LSTM", "PERSISTENCE_VELOCITY")
    assert len(out["predicted_points"]) == 3
    for p, h in zip(out["predicted_points"], [24, 72, 168]):
        assert p["forecast_hour"] == h
        assert "lat" in p and "lon" in p
        assert -90 <= p["lat"] <= 90
        assert -180 <= p["lon"] <= 180


def test_trajectory_predictor_handles_short_track_gracefully():
    from app.ml.iceberg_trajectory import IcebergTrajectoryPredictor
    pred = IcebergTrajectoryPredictor()
    pts = _make_track(n=1)  # far too short for any real model
    out = pred.predict("SHORT", pts, forecast_hours=[24])
    assert len(out["predicted_points"]) == 1
    # Falls back to holding position rather than crashing or fabricating motion.
    assert out["predicted_points"][0]["lat"] == pts[0]["lat"]


def test_trajectory_predictor_never_claims_lstm_without_trained_weights(monkeypatch):
    from app.ml import iceberg_trajectory as traj_mod
    monkeypatch.setattr(traj_mod.LSTMTrajectoryModel, "__init__", lambda self: setattr(self, "model", None))
    pred = traj_mod.IcebergTrajectoryPredictor()
    assert pred.model_status == "PERSISTENCE_VELOCITY"
    out = pred.predict("X", _make_track(), forecast_hours=[24])
    assert out["model_type"] == "PERSISTENCE_VELOCITY"


def test_cfar_detector_never_labels_output_as_confirmed():
    from app.ml.iceberg_detector import CFARDetector
    rng = np.random.default_rng(0)
    db = rng.normal(-20, 1.0, (60, 60)).astype(np.float64)
    db[30, 30] = 5.0  # one bright compact target
    # Minimal but correctly-shaped geolocation grid for rowcol_to_ll.
    rows = np.array([0, 30, 60])
    cols = np.array([0, 30, 60])
    lats = np.array([[-64.0, -64.0, -64.0], [-65.0, -65.0, -65.0], [-66.0, -66.0, -66.0]])
    lons = np.array([[-62.0, -60.0, -58.0]] * 3)
    geo = {"rows": rows, "cols": cols, "lats": lats.ravel(), "lons": lons.ravel()}
    preview = {"sigma0_db": db, "geo": geo, "stride": 1}
    cands = CFARDetector().detect_from_preview(preview)
    for c in cands:
        assert c["source"] == "S1_CFAR"
        assert 0.0 <= c["confidence"] <= 1.0
        assert -90 <= c["lat"] <= 90 and -180 <= c["lon"] <= 180


def test_seaice_forecaster_reports_convlstm_not_trained():
    from app.ml.sea_ice_forecast import SeaIceForecaster
    fc = SeaIceForecaster()
    assert fc.check_training_data() is False
    assert fc.model_status != "CONVLSTM"


def test_seaice_backtest_next_day_measures_real_mae():
    from app.ml.sea_ice_forecast import backtest_next_day
    rng = np.random.default_rng(1)
    stack = np.clip(rng.normal(50, 5, (5, 10, 10)), 0, 100)
    result = backtest_next_day(stack)
    assert result["persistence_mae_pairs"] > 0
    assert result["persistence_mae_fraction"] is not None
    assert result["persistence_mae_fraction"] >= 0


# ── Pipeline/risk integration tests (synthetic pipeline state) ─────────────

def test_risk_map_includes_new_explainable_fields(synthetic_ocean_with_predictions):
    resp = RiskService().generate_risk_map()
    assert "risk_range" in resp and resp["risk_range"]["min"] is not None
    assert "crs" in resp and "api_crs" in resp
    assert resp["overlay"]["url"] == "/api/overlays/risk.png"
    assert "generated_at" in resp
    assert resp["forecast_horizon_hours"] in (24, 72, 168)
    assert "warnings" in resp
    assert set(resp["provenance"]["weights"].keys()) == {"ice", "iceberg", "weather", "bathymetry", "current"}


def test_risk_grid_stays_within_0_100_with_all_components_active(synthetic_ocean_with_predictions, grid):
    RiskService().generate_risk_map()
    finite = grid.risk_grid[np.isfinite(grid.risk_grid)]
    assert finite.min() >= 0.0
    assert finite.max() <= 100.0


def test_risk_components_sum_to_total_risk(synthetic_ocean_with_predictions, grid):
    RiskService().generate_risk_map()
    assert grid.risk_components, "risk_components should be populated"
    summed = sum(grid.risk_components.values())
    valid = np.isfinite(grid.risk_grid) & np.isfinite(summed)
    assert np.allclose(summed[valid], grid.risk_grid[valid], atol=1e-6)


def test_predicted_iceberg_increases_risk_near_forecast_position(synthetic_ocean_with_predictions, grid):
    RiskService().generate_risk_map()
    mid_i, mid_j = grid.latlon_to_indices(-64.5, -57.5)
    near_risk = grid.risk_components["iceberg_predicted"][mid_i, mid_j]
    far_risk = grid.risk_components["iceberg_predicted"][0, 0]
    assert near_risk > far_risk


def test_predicted_iceberg_risk_uses_confidence_discount_not_full_weight(synthetic_ocean_with_predictions, grid):
    """Predictions must never be treated as guaranteed (Phase 3): the
    predicted-position contribution near the forecast berg should be less
    than what a *confirmed* berg at the same distance would contribute.
    """
    RiskService().generate_risk_map()
    mid_i, mid_j = grid.latlon_to_indices(-64.5, -57.5)
    predicted_contrib = grid.risk_components["iceberg_predicted"][mid_i, mid_j]
    # Same weight bucket as a confirmed berg at ~0 distance would be w_iceberg*100.
    from app.core.config import get_settings
    full_weight_contrib = get_settings().RISK_WEIGHT_ICEBERG * 100.0
    assert predicted_contrib < full_weight_contrib


def test_risk_map_reports_horizon_fallback_warning_for_unsupported_horizon(synthetic_ocean_with_predictions):
    resp = RiskService().generate_risk_map(forecast_horizon_hours=999)
    assert any("not computed" in w or "nearest available" in w for w in resp["warnings"])


def test_risk_map_reports_missing_current_data(synthetic_ocean, grid):
    grid.current_speed = np.full(grid.grid_shape, np.nan)
    resp = RiskService().generate_risk_map()
    assert any("current" in w.lower() for w in resp["warnings"])


def test_risk_map_reports_missing_nowcast_when_unavailable(synthetic_ocean):
    # synthetic_ocean (without predictions fixture) leaves ensure_loaded()
    # returning a minimal state with no "nowcast" key.
    resp = RiskService().generate_risk_map()
    assert any("nowcast" in w.lower() for w in resp["warnings"])


def test_risk_map_caches_identical_requests(synthetic_ocean_with_predictions):
    r1 = RiskService().generate_risk_map()
    assert r1["cached"] is False
    r2 = RiskService().generate_risk_map()
    assert r2["cached"] is True


def test_risk_map_cache_invalidates_when_grid_data_changes(synthetic_ocean_with_predictions, grid):
    r1 = RiskService().generate_risk_map()
    assert r1["cached"] is False
    grid.wind_speed = grid.wind_speed + 10.0
    r2 = RiskService().generate_risk_map()
    assert r2["cached"] is False  # data changed -> must recompute, not serve stale


# ── Route-level integration: predicted iceberg penalty + breakdown ─────────

def test_route_includes_risk_breakdown_and_primary_hazard(od_points, synthetic_ocean_with_predictions):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "BALANCED")
    assert not r["fallback"]
    assert r["risk_breakdown"] is not None
    for key in ("sea_ice", "iceberg_current", "iceberg_predicted", "weather", "bathymetry", "current", "iceberg_total", "total"):
        assert key in r["risk_breakdown"]
    assert r["primary_hazard"] is not None and r["primary_hazard"].startswith("Primary Hazard:")
    assert abs(r["risk_breakdown"]["total"] - r["risk_score"]) < 1e-6


def test_route_reports_forecast_horizon_and_uncertainty(od_points, synthetic_ocean_with_predictions):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    assert r["forecast_horizon_hours"] in (24, 72, 168)
    assert r["predicted_iceberg_uncertainty_km"] is not None


def test_route_avoids_predicted_iceberg_when_safest(od_points, synthetic_ocean_with_predictions, grid):
    """SAFEST should route around the predicted-iceberg hotspot placed at the
    grid midpoint by the fixture, exactly as it already does for current ice.
    """
    fastest = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "FASTEST")
    safest = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "SAFEST")
    assert not fastest["fallback"] and not safest["fallback"]
    assert safest["risk_score"] <= fastest["risk_score"] + 1e-6


def test_route_warns_about_forecast_based_predicted_iceberg(od_points, synthetic_ocean_with_predictions):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "BALANCED")
    assert r["risk_breakdown"]["iceberg_predicted"] > 0
    assert any("forecast" in w.lower() or "predicted" in w.lower() for w in r["warnings"])


def test_data_availability_reports_predicted_iceberg_and_nowcast_flags(od_points, synthetic_ocean_with_predictions):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "BALANCED")
    assert r["data_availability"]["predicted_iceberg_positions"] is True
    assert r["data_availability"]["sea_ice_nowcast"] is True


def test_data_availability_false_when_predicted_iceberg_missing(od_points, synthetic_ocean):
    r = generate_route(Point(**od_points["origin"]), Point(**od_points["destination"]), "BALANCED")
    assert r["data_availability"]["predicted_iceberg_positions"] is False
    assert r["data_availability"]["sea_ice_nowcast"] is False


# ── API endpoint tests ──────────────────────────────────────────────────────

def test_risk_map_endpoint_returns_overlay_crs_and_range(client):
    r = client.get("/api/risk-map")
    assert r.status_code == 200
    body = r.json()
    assert "overlay" in body and body["overlay"]["url"] == "/api/overlays/risk.png"
    assert "crs" in body
    assert "risk_range" in body
    assert "generated_at" in body


def test_risk_map_endpoint_accepts_forecast_horizon_and_weight_overrides(client):
    r = client.get("/api/risk-map?forecast_horizon_hours=72&iceberg_weight=0.5")
    assert r.status_code == 200
    body = r.json()
    assert body["provenance"]["weights"]["iceberg"] == 0.5


def test_icebergs_endpoint_labels_categories(client):
    r = client.get("/api/icebergs")
    assert r.status_code == 200
    body = r.json()
    assert "icebergs" in body and "count" in body


def test_ml_status_endpoint_returns_structured_model_info(client):
    r = client.get("/api/ml/status")
    assert r.status_code == 200
    body = r.json()
    assert "iceberg_trajectory" in body
    assert "sar_iceberg_detection" in body
    assert "sea_ice_nowcast" in body
    assert body["sar_iceberg_detection"]["model_status"] == "CFAR"
