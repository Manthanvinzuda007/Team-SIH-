"""Sea-ice nowcast.

This bundle has 8 consecutive AMSR2 days (2026-08-01..08). That is enough for a
persistence vs. optical-flow advection backtest of next-day fields (7 pairs).
It is NOT enough to train a ConvLSTM with any credible generalization claim.
ConvLSTMModel.check_training_data() therefore returns False.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.geo import field_stats

logger = logging.getLogger("polaris")


class PersistenceModel:
    def predict(self, current_grid, hours=24):
        return np.array(current_grid, copy=True)


class ConvLSTMModel:
    def __init__(self):
        self.reason = (
            "Only 8 daily SH concentration fields are on disk. A ConvLSTM is not "
            "trained. Persistence + Farneback advection are the implemented models."
        )

    def check_training_data(self) -> bool:
        return False


def _advect(prev: np.ndarray, curr: np.ndarray, hours: float) -> np.ndarray:
    """Warp `curr` forward by (hours/24) of the Farneback flow prev→curr.

    Flow is computed on valid concentration (0–1). Land/NaN is filled with 0 for
    the flow solver only.
    """
    import cv2

    a = np.nan_to_num(prev.astype(np.float32), nan=0.0)
    b = np.nan_to_num(curr.astype(np.float32), nan=0.0)
    flow = cv2.calcOpticalFlowFarneback(
        a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0
    )
    scale = float(hours) / 24.0
    h, w = curr.shape
    gx, gy = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (gx + flow[..., 0] * scale).astype(np.float32)
    map_y = (gy + flow[..., 1] * scale).astype(np.float32)
    warped = cv2.remap(b, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    out = warped.astype(np.float64)
    out[~np.isfinite(curr)] = np.nan
    return out


def backtest_next_day(stack: np.ndarray) -> Dict[str, Any]:
    """Predict day t+1 from days ≤ t. Returns measured MAE on valid ice pixels.

    stack: (T, Y, X) ice fraction with NaN land.
    With T=8 we get 7 persistence pairs and 6 advection pairs (need t-1, t → t+1).
    """
    T = stack.shape[0]
    pers_mae = []
    adv_mae = []
    for t in range(T - 1):
        pred = stack[t]
        truth = stack[t + 1]
        m = np.isfinite(pred) & np.isfinite(truth)
        if m.sum() < 100:
            continue
        pers_mae.append(float(np.mean(np.abs(pred[m] - truth[m]))))
    for t in range(1, T - 1):
        pred = _advect(stack[t - 1], stack[t], hours=24.0)
        truth = stack[t + 1]
        m = np.isfinite(pred) & np.isfinite(truth)
        if m.sum() < 100:
            continue
        adv_mae.append(float(np.mean(np.abs(pred[m] - truth[m]))))
    result = {
        "n_days": int(T),
        "persistence_mae_pairs": len(pers_mae),
        "advection_mae_pairs": len(adv_mae),
        "persistence_mae_fraction": float(np.mean(pers_mae)) if pers_mae else None,
        "advection_mae_fraction": float(np.mean(adv_mae)) if adv_mae else None,
        "persistence_mae_list": pers_mae,
        "advection_mae_list": adv_mae,
        "units": "ice-concentration fraction (0-1) on native AMSR2 grid",
        "note": "Measured against the 8 real files. Not a published skill score beyond this window.",
    }
    logger.info("SEAICE BACKTEST %s", {k: result[k] for k in ("persistence_mae_fraction", "advection_mae_fraction", "persistence_mae_pairs", "advection_mae_pairs")})
    return result


class SeaIceForecaster:
    def __init__(self):
        self.model_status = "ADVECTION"  # proposed; ConvLSTM is not trained
        self.persistence = PersistenceModel()
        self.convlstm = ConvLSTMModel()
        self.metrics: Dict[str, Any] = {}
        self._stack = None

    def check_training_data(self) -> bool:
        return self.convlstm.check_training_data()

    def set_native_stack(self, stack: np.ndarray):
        self._stack = stack
        self.metrics = backtest_next_day(stack)

    def predict(self, current_state, forecast_hours=None):
        forecast_hours = forecast_hours or [6, 12, 24]
        curr = np.asarray(current_state, dtype=np.float64)
        mae = self.metrics.get("advection_mae_fraction") or self.metrics.get("persistence_mae_fraction")
        # Tie base confidence to measured MAE when available. MAE of 0.05 → ~0.9; 0.25 → 0.5.
        if mae is not None:
            base = float(np.clip(1.0 - mae / 0.5, 0.35, 0.92))
        else:
            base = 0.5  # unknown — not a claimed accuracy
        prev = None
        if self._stack is not None and self._stack.shape[0] >= 2:
            prev = self._stack[-2]
            curr_native = self._stack[-1]
        else:
            curr_native = curr
        predictions = []
        for h in forecast_hours:
            if prev is not None and h > 0:
                grid = _advect(prev, curr_native, hours=float(h))
                mtype = "OPTICAL_FLOW_ADVECTION"
            else:
                grid = self.persistence.predict(curr_native, h)
                mtype = "PERSISTENCE"
            conf = float(np.clip(base - (h / 100.0), 0.15, 0.95))
            predictions.append({
                "forecast_hour": h,
                "data_grid": grid,
                "confidence": conf,
                "model_type": mtype,
                "metrics": {
                    "MAE_fraction_backtest": mae,
                    "MAE_source": "next-day backtest on 8 AMSR2 days" if mae is not None else "not computed",
                },
                "horizon_note": "Honest horizon is ~24–48 h with this 8-day corpus; confidence decays with hour.",
            })
        return predictions
