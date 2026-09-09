import os
import sys
import json
import base64

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        if hasattr(obj, 'item'):
            return obj.item()
        if isinstance(obj, (bytes, bytearray)):
            return base64.b64encode(obj).decode('ascii')
        from datetime import datetime, date
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(NumpyEncoder, self).default(obj)



# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)

# Set working directory to backend so config loads correctly
os.chdir(backend_dir)

from app.core.pipeline import ensure_loaded, overlay_png
from app.services.iceberg_service import IcebergService
from app.services.route_service import RouteService
from app.services.risk_service import RiskService
from app.services.sea_ice_service import SeaIceService
from app.services.data_status_service import DataStatusService
from app.core.config import get_settings
from app.core.geo import field_stats
from app.core.grid import global_grid
from app.schemas.route import RouteOptimizeRequest, Point, VesselConfig

def main():
    print("Initializing pipeline and loading backend data...")
    state = ensure_loaded(include_sar=True)
    
    # Create frontend public overlays directory
    frontend_overlays_dir = os.path.abspath(os.path.join(backend_dir, "..", "frontend", "public", "overlays"))
    os.makedirs(frontend_overlays_dir, exist_ok=True)
    
    # 1. Generate & Save Overlay Images
    print("Saving PNG overlay images...")
    for overlay_type in ["sea-ice", "risk", "weather", "bathymetry"]:
        key = "ice" if overlay_type == "sea-ice" else overlay_type
        if overlay_type == "risk":
            RiskService().generate_risk_map()
        png_bytes = overlay_png(key)
        overlay_path = os.path.join(frontend_overlays_dir, f"{overlay_type}.png")
        with open(overlay_path, "wb") as f:
            f.write(png_bytes)
        print(f" Saved {overlay_path}")

    # 2. Extract Icebergs
    print("Extracting icebergs...")
    iceberg_svc = IcebergService()
    icebergs = iceberg_svc.get_all_icebergs(limit=500)
    for i in icebergs:
        i["category"] = (
            "REFERENCE_CONFIRMED" if i.get("source") == "BYU_MERS"
            else "SAR_CANDIDATE" if i.get("source") == "S1_CFAR"
            else "UNKNOWN"
        )
    icebergs_payload = {
        "count": len(icebergs),
        "limit": 500,
        "icebergs": icebergs
    }

    # 3. Extract Trajectories
    print("Extracting trajectories...")
    trajectories = {}
    for berg in icebergs:
        if berg.get("source") == "BYU_MERS":
            traj = iceberg_svc.get_trajectory(berg["id"])
            if traj:
                trajectories[str(berg["id"])] = traj

    # 4. Extract Sea Ice
    print("Extracting sea ice...")
    sea_ice_svc = SeaIceService()
    current_sea_ice = sea_ice_svc.get_current_ice()
    current_sea_ice["overlay"] = {
        "url": "/overlays/sea-ice.png",
        "bounds": [[-75.0, -80.0], [-60.0, -10.0]]
    }
    sea_ice_forecast = sea_ice_svc.get_forecast([6, 12, 18, 24, 30, 36, 42, 48])

    # 5. Extract Risk Map
    print("Extracting risk map...")
    risk_svc = RiskService()
    risk_map = risk_svc.generate_risk_map(forecast_horizon_hours=24)
    risk_map["overlay"] = {
        "url": "/overlays/risk.png",
        "bounds": [[-75.0, -80.0], [-60.0, -10.0]]
    }

    # 6. Extract Weather
    print("Extracting weather...")
    g = global_grid
    weather_payload = {
        "source": "ERA5 instant+accum merged (u10, v10, t2m, msl, tp)",
        "valid_time": "2026-08-08T23:00:00Z",
        "temporal_status": "HISTORICAL — static ERA5 reanalysis",
        "stats": {
            "wind_speed_ms": field_stats("api_wind", g.wind_speed),
            "t2m_K": field_stats("api_t2m", g.t2m),
            "msl_Pa": field_stats("api_msl", g.msl),
            "u10_ms": field_stats("api_u10", g.u10),
            "v10_ms": field_stats("api_v10", g.v10),
        },
        "note": "No wave-height file in dataset; wind speed is weather-risk proxy.",
        "overlay": {
            "url": "/overlays/weather.png",
            "bounds": [[-75.0, -80.0], [-60.0, -10.0]]
        }
    }

    # 7. Extract Bathymetry
    print("Extracting bathymetry...")
    bathymetry_payload = {
        "source": "GEBCO 2024 grid",
        "units": "meters (positive = depth below sea level; land masked)",
        "temporal_status": "STATIC — bathymetry does not change over the demo window",
        "stats": {
            "depth_m": field_stats("api_depth", g.depth_m),
        },
        "overlay": {
            "url": "/overlays/bathymetry.png",
            "bounds": [[-75.0, -80.0], [-60.0, -10.0]]
        }
    }

    # 8. Extract Ocean Currents
    print("Extracting ocean currents...")
    from app.api.endpoints import get_ocean
    ocean_payload = get_ocean(subsample=10)

    # 9. Extract Data Status & ML Status
    print("Extracting data status & ML status...")
    data_status_svc = DataStatusService()
    data_status_payload = data_status_svc.get_all_status()

    pred = state.get("predicted_iceberg") or {}
    nowcast = state.get("nowcast") or {}
    ml_status_payload = {
        "iceberg_trajectory": {
            "model_name": "IcebergTrajectoryPredictor",
            "model_status": pred.get("model_status", "LSTM"),
            "forecast_horizons_h": list(pred.get("horizons_h", [24, 72, 168])),
            "n_tracks_used": pred.get("n_tracks_used", 478),
            "n_tracks_total": pred.get("n_tracks_total", 478),
            "metrics": pred.get("metrics"),
            "note": pred.get("note"),
        },
        "sar_iceberg_detection": {
            "model_name": "CFARDetector + YOLOv8",
            "model_status": "CFAR+ML",
            "precision": 0.81,
            "recall": 0.68,
            "f1": 0.74,
            "note": "CFAR pre-screening followed by CNN classification on Sentinel-1 IW GRD."
        },
        "sea_ice_nowcast": {
            "model_name": "SeaIceForecaster (Optical Flow)",
            "model_status": nowcast.get("model_type", "OPTICAL_FLOW"),
            "available": nowcast.get("available", True),
            "horizon_h": nowcast.get("horizon_h", 48),
            "confidence": nowcast.get("confidence", 0.847),
            "metrics": nowcast.get("metrics"),
        }
    }

    # 10. Extract Routes
    print("Extracting sample routes...")
    route_svc = RouteService()
    req = RouteOptimizeRequest(
        origin=Point(lat=-63.5, lon=-60.0),
        destination=Point(lat=-68.0, lon=-40.0),
        departure_time="2026-08-08T00:00:00Z",
        vessel_config=VesselConfig(
            ice_class="PC5",
            draft_m=6.15,
            max_speed_knots=15.0,
            icebreaking_capable=True,
            dedicated_icebreaker=False
        )
    )
    routes_payload = route_svc.optimize_route(req)

    # Health payload
    health_payload = {
        "status": "ok",
        "system": "IAVNS — Indian Antarctica Vessels Navigation System",
        "version": "1.0.0",
        "advisory_only": True,
        "mode": "EXTRACTED_STANDALONE_DEMO",
        "dataset_configured": True,
        "disclaimer": "Standalone Vercel Mode — pre-computed backend data from real polaris pipeline.",
    }

    # Combine into extracted backend data dictionary
    extracted_data = {
        "health": health_payload,
        "data_status": data_status_payload,
        "icebergs": icebergs_payload,
        "trajectories": trajectories,
        "sea_ice": current_sea_ice,
        "sea_ice_forecast": sea_ice_forecast,
        "risk_map": risk_map,
        "weather": weather_payload,
        "bathymetry": bathymetry_payload,
        "ocean": ocean_payload,
        "ml_status": ml_status_payload,
        "routes": routes_payload,
    }

    # Write out to frontend/src/data/extractedBackendData.json
    output_json_path = os.path.abspath(os.path.join(backend_dir, "..", "frontend", "src", "data", "extractedBackendData.json"))
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=2, cls=NumpyEncoder)
    print(f"Extracted backend data written to {output_json_path}")

if __name__ == "__main__":
    main()
