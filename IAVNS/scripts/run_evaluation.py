#!/usr/bin/env python3
"""Run loaders against real files, train/eval trajectory LSTM, write EVALUATION.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.config import get_settings
from app.core.grid import global_grid
from app.core.pipeline import ensure_loaded
from app.ml.iceberg_trajectory import evaluate_split
from app.services.risk_service import RiskService
from app.services.route_service import RouteService
from app.schemas.route import RouteOptimizeRequest, Point
from datetime import datetime


def md_num(x, nd=3):
    if x is None:
        return "n/a (not computed)"
    return f"{x:.{nd}f}"


def main():
    s = get_settings()
    print("DATASET_PATH", s.DATASET_PATH, "exists", Path(s.DATASET_PATH).exists())
    print("Grid", global_grid.shape, "valid_frac", float(global_grid.valid.mean()),
          "res_km", global_grid.resolution_km)

    st = ensure_loaded(include_sar=True)
    ice = st["forecaster"].metrics
    print("SEAICE BACKTEST", json.dumps(ice, indent=2))
    print("SAR candidates", len(st["sar_candidates"]))
    print("BYU tracks", len(st["tracks"]))

    print("Training LSTM on BYU hold-out split…")
    traj = evaluate_split(st["tracks"], holdout_frac=0.15, seed=7)
    print("TRAJECTORY", json.dumps(traj["ADE_km"], indent=2))

    RiskService().generate_risk_map()
    origin = Point(lat=-63.5, lon=-60.0)
    dest = Point(lat=-68.0, lon=-40.0)
    req = RouteOptimizeRequest(
        origin=origin, destination=dest, departure_time=datetime(2026, 8, 8),
        vessel_config={"ice_class": "PC1", "draft_m": 8.0, "icebreaker": True},
    )
    routes = RouteService().optimize_route(req)["routes"]
    for r in routes:
        print(r["mode"], "nm", r.get("distance_nm"), "risk", r.get("risk_score"),
              "fallback", r.get("fallback"), r.get("fallback_reason"), r.get("explanation_text", "")[:160])

    out = Path(__file__).parent.parent / "EVALUATION.md"
    ade = traj["ADE_km"]
    lines = f"""# POLARIS evaluation (computed on this machine)

**Dataset root:** `{s.DATASET_PATH}`  
**Analysis grid:** EPSG:3031, {global_grid.resolution_km} km, shape {global_grid.shape}, valid cell fraction {float(global_grid.valid.mean()):.3f}, AOI lat [{global_grid.lat_min}, {global_grid.lat_max}] lon [{global_grid.lon_min}, {global_grid.lon_max}].

These numbers come from running the code against the files on disk. They are **not** literature scores and are **not** a claim of operational skill outside this bundle.

## 1. Sea-ice next-day nowcast (8 AMSR2 days, 2026-08-01 … 08)

Native grid: 332 × 316, EPSG:3412, 25 km, variable `ICECON` (fraction; flags &gt; 1.005 masked).

| Model | Pairs | MAE (concentration fraction) |
|---|---|---|
| Persistence (day t → t+1) | {ice.get('persistence_mae_pairs')} | {md_num(ice.get('persistence_mae_fraction'), 4)} |
| Farneback optical-flow advection | {ice.get('advection_mae_pairs')} | {md_num(ice.get('advection_mae_fraction'), 4)} |

Per-pair persistence MAE: {ice.get('persistence_mae_list')}  
Per-pair advection MAE: {ice.get('advection_mae_list')}

A ConvLSTM is **not** trained. Eight days cannot support that claim. Forecast API horizon is treated as ~24–48 h with confidence tied to this MAE.

## 2. Iceberg trajectory (BYU 647 tracks, iceberg-level hold-out)

Usable tracks: {traj.get('n_tracks_total_usable')} · train icebergs: {traj.get('n_train_icebergs')} · test icebergs: {traj.get('n_test_icebergs')} · LSTM windows (capped): {traj.get('n_lstm_windows')} · eval samples: {traj.get('n_eval_samples')} · trained: {traj.get('trained')}

Split: **hold out ~15% of icebergs**, not random points (avoids leakage).

| Horizon | Baseline ADE (persistence-of-velocity, km) | LSTM ADE (km) |
|---|---|---|
| +1 day | {md_num(ade['1d']['baseline_persistence_velocity'], 2)} | {md_num(ade['1d']['lstm'], 2)} |
| +3 day | {md_num(ade['3d']['baseline_persistence_velocity'], 2)} | {md_num(ade['3d']['lstm'], 2)} |
| +7 day | {md_num(ade['7d']['baseline_persistence_velocity'], 2)} | {md_num(ade['7d']['lstm'], 2)} |

FDE at each horizon equals ADE here (single endpoint after h-day rollout).  
Wind/current “2% of wind” is **not** the reported baseline: ERA5 is ~8 days and GLORYS is June 2026 only — they do not match the multi-decade BYU corpus.

## 3. SAR iceberg detector (one Sentinel-1 IW GRD HH scene, 2026-08-22)

Calibrated σ⁰ from `calibration-*.xml` (DN is not treated as backscatter). CFAR-style bright compact blobs on a stride-16 preview.

**Candidate count:** {len(st['sar_candidates'])}

**Precision/recall:** not reported. There are no independent labels for this scene. Any precision number would be fabricated. YOLO is not trained.

## 4. Example routes (PC1 icebreaker, draft 8 m)

Origin {origin.lat}, {origin.lon} → destination {dest.lat}, {dest.lon} (inside the analysis AOI).

| Mode | Distance (NM) | Mean risk / 100 | Fuel-proxy (t) | Fallback |
|---|---|---|---|---|
"""
    for r in routes:
        lines += f"| {r['mode']} | {r.get('distance_nm')} | {r.get('risk_score')} | {r.get('fuel_tonnes')} | {r.get('fallback_reason') or 'A* path'} |\n"
    lines += "\nFuel-proxy uses a **design factor** 0.13 t/NM, not measured consumption.\n"
    lines += "\n### Explanations (from segment-level comparison)\n\n"
    for r in routes:
        lines += f"- **{r['mode']}:** {r.get('explanation_text')}\n"
    lines += """
## What this corpus cannot support

- Training a ConvLSTM / global 1 km ice model
- Multi-temporal SAR change detection (one scene)
- Real-time satellite ingestion (static files)
- Accident-rate calibrated risk (weighted overlay of available fields only)
"""
    out.write_text(lines, encoding="utf-8")
    print("Wrote", out)


if __name__ == "__main__":
    main()
