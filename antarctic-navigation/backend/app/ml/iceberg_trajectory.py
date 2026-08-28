"""Iceberg trajectory models trained on BYU tracks.

Forcing-based 2%-of-wind + current is NOT a fair baseline here: we only have
~2 weeks of ERA5 and 8 June days of GLORYS, not multi-decade reanalysis aligned
to each historical fix. The fair baseline is persistence-of-velocity on each
held-out track.

The LSTM is trained across icebergs (hold out ~15% of *icebergs*, not random
points, to avoid leakage). ADE/FDE are computed on that split.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.core.geo import field_stats, haversine_km

logger = logging.getLogger("polaris")

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
SEQ_LEN = 7
HORIZONS_DAYS = (1, 3, 7)


def _parse_ts(p) -> datetime:
    ts = p["timestamp"]
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(str(ts).replace("Z", ""))


def track_to_arrays(points: List[Dict[str, Any]]) -> Optional[Dict[str, np.ndarray]]:
    if len(points) < SEQ_LEN + max(HORIZONS_DAYS) + 1:
        return None
    pts = sorted(points, key=_parse_ts)
    lats = np.array([p["lat"] for p in pts], dtype=np.float64)
    lons = np.array([p["lon"] for p in pts], dtype=np.float64)
    times = [_parse_ts(p) for p in pts]
    dt = np.array([(times[i] - times[i - 1]).total_seconds() / 86400.0 for i in range(1, len(times))])
    dt = np.concatenate([[1.0], dt])
    return {"lat": lats, "lon": lons, "t": times, "dt": dt}


def _features_at(lat, lon, t: datetime, dlat, dlon) -> np.ndarray:
    doy = t.timetuple().tm_yday
    return np.array([
        lat / 90.0,
        lon / 180.0,
        math.sin(2 * math.pi * doy / 365.25),
        math.cos(2 * math.pi * doy / 365.25),
        dlat,
        dlon,
    ], dtype=np.float64)


class ConstantVelocityModel:
    """Persistence-of-velocity using the last observed step, scaled by its dt."""

    def predict_days(self, points: List[Dict[str, Any]], days: List[int]) -> List[Dict[str, Any]]:
        if not points or len(points) < 2:
            last = points[-1] if points else None
            if not last:
                return []
            return [{"forecast_day": d, "lat": last["lat"], "lon": last["lon"]} for d in days]
        p1, p2 = points[-2], points[-1]
        t1, t2 = _parse_ts(p1), _parse_ts(p2)
        dt_days = max((t2 - t1).total_seconds() / 86400.0, 1e-3)
        dlat = (p2["lat"] - p1["lat"]) / dt_days
        dlon = (p2["lon"] - p1["lon"]) / dt_days
        out = []
        for d in days:
            out.append({
                "forecast_day": d,
                "forecast_hour": int(d * 24),
                "lat": p2["lat"] + dlat * d,
                "lon": p2["lon"] + dlon * d,
            })
        return out

    def predict(self, historical_positions, hours_ahead):
        days = [max(1, int(round(h / 24.0))) for h in hours_ahead]
        pred = self.predict_days(historical_positions, days)
        for p, h in zip(pred, hours_ahead):
            p["forecast_hour"] = h
        return pred


class NumpyLSTM:
    """Minimal 1-layer LSTM (input_size=6, hidden=H) trained with Adam on MSE of (dlat, dlon)."""

    def __init__(self, input_size=6, hidden=24, seed=0):
        rng = np.random.default_rng(seed)
        self.hidden = hidden
        self.input_size = input_size
        scale = 0.08
        self.W = rng.normal(0, scale, (input_size + hidden, 4 * hidden))
        self.b = np.zeros(4 * hidden)
        self.Why = rng.normal(0, scale, (hidden, 2))
        self.by = np.zeros(2)

    def _step(self, x, h, c):
        z = np.concatenate([x, h]) @ self.W + self.b
        H = self.hidden
        i = 1 / (1 + np.exp(-z[:H]))
        f = 1 / (1 + np.exp(-z[H:2 * H]))
        o = 1 / (1 + np.exp(-z[2 * H:3 * H]))
        g = np.tanh(z[3 * H:])
        c2 = f * c + i * g
        h2 = o * np.tanh(c2)
        return h2, c2, (i, f, o, g, z)

    def forward(self, seq: np.ndarray) -> np.ndarray:
        h = np.zeros(self.hidden)
        c = np.zeros(self.hidden)
        for t in range(seq.shape[0]):
            h, c, _ = self._step(seq[t], h, c)
        return h @ self.Why + self.by

    def predict_delta(self, seq: np.ndarray) -> np.ndarray:
        return self.forward(seq)

    def _loss_grad(self, seq, target, clip=5.0):
        # forward storing activations
        hs = [np.zeros(self.hidden)]
        cs = [np.zeros(self.hidden)]
        caches = []
        h, c = hs[0], cs[0]
        for t in range(seq.shape[0]):
            h, c, cache = self._step(seq[t], h, c)
            hs.append(h)
            cs.append(c)
            caches.append(cache)
        y = hs[-1] @ self.Why + self.by
        diff = y - target
        loss = float(np.mean(diff ** 2))
        dy = (2.0 / diff.size) * diff
        dWhy = np.outer(hs[-1], dy)
        dby = dy
        dh = self.Why @ dy
        dc = np.zeros(self.hidden)
        dW = np.zeros_like(self.W)
        db = np.zeros_like(self.b)
        H = self.hidden
        for t in reversed(range(seq.shape[0])):
            i, f, o, g, z = caches[t]
            c_prev, c_cur = cs[t], cs[t + 1]
            h_prev = hs[t]
            do = dh * np.tanh(c_cur)
            dc += dh * o * (1 - np.tanh(c_cur) ** 2)
            df = dc * c_prev
            di = dc * g
            dg = dc * i
            dc = dc * f
            dz = np.zeros(4 * H)
            dz[:H] = di * i * (1 - i)
            dz[H:2 * H] = df * f * (1 - f)
            dz[2 * H:3 * H] = do * o * (1 - o)
            dz[3 * H:] = dg * (1 - g ** 2)
            xh = np.concatenate([seq[t], h_prev])
            dW += np.outer(xh, dz)
            db += dz
            dxh = self.W @ dz
            dh = dxh[self.input_size:]
        # clip
        for arr in (dW, db, dWhy, dby):
            np.clip(arr, -clip, clip, out=arr)
        return loss, dW, db, dWhy, dby

    def train(self, sequences: np.ndarray, targets: np.ndarray, epochs=12, lr=0.01, batch=64):
        n = sequences.shape[0]
        mW = np.zeros_like(self.W); vW = np.zeros_like(self.W)
        mb = np.zeros_like(self.b); vb = np.zeros_like(self.b)
        mY = np.zeros_like(self.Why); vY = np.zeros_like(self.Why)
        my = np.zeros_like(self.by); vy = np.zeros_like(self.by)
        b1, b2, eps = 0.9, 0.999, 1e-8
        tstep = 0
        hist = []
        rng = np.random.default_rng(1)

        def adam(p, g, m, v):
            m[:] = b1 * m + (1 - b1) * g
            v[:] = b2 * v + (1 - b2) * (g ** 2)
            mhat = m / (1 - b1 ** tstep)
            vhat = v / (1 - b2 ** tstep)
            p -= lr * mhat / (np.sqrt(vhat) + eps)

        for ep in range(epochs):
            idx = rng.permutation(n)
            losses = []
            for start in range(0, n, batch):
                sl = idx[start:start + batch]
                gW = np.zeros_like(self.W); gb = np.zeros_like(self.b)
                gY = np.zeros_like(self.Why); gy = np.zeros_like(self.by)
                acc = 0.0
                for j in sl:
                    loss, dW, db, dWhy, dby = self._loss_grad(sequences[j], targets[j])
                    acc += loss
                    gW += dW; gb += db; gY += dWhy; gy += dby
                k = max(len(sl), 1)
                tstep += 1
                adam(self.W, gW / k, mW, vW)
                adam(self.b, gb / k, mb, vb)
                adam(self.Why, gY / k, mY, vY)
                adam(self.by, gy / k, my, vy)
                losses.append(acc / k)
            hist.append(float(np.mean(losses)))
            logger.info("LSTM epoch %s/%s loss=%.6f n=%s", ep + 1, epochs, hist[-1], n)
        return hist

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, W=self.W, b=self.b, Why=self.Why, by=self.by, hidden=self.hidden)

    @classmethod
    def load(cls, path: Path) -> "NumpyLSTM":
        z = np.load(path)
        m = cls(hidden=int(z["hidden"]))
        m.W, m.b, m.Why, m.by = z["W"], z["b"], z["Why"], z["by"]
        return m


def build_windows(tracks: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    seqs, targs, names = [], [], []
    for tr in tracks:
        arr = track_to_arrays(tr["points"])
        if arr is None:
            continue
        lat, lon, times, dt = arr["lat"], arr["lon"], arr["t"], arr["dt"]
        dlat = np.diff(lat, prepend=lat[0])
        dlon = np.diff(lon, prepend=lon[0])
        ok_dt = (dt >= 0.4) & (dt <= 3.0)
        for i in range(1, len(lat) - 1):
            if i < SEQ_LEN:
                continue
            sl = slice(i - SEQ_LEN, i)
            if not np.all(ok_dt[i - SEQ_LEN + 1:i + 1]):
                continue
            feats = np.stack([
                _features_at(lat[k], lon[k], times[k], dlat[k], dlon[k]) for k in range(i - SEQ_LEN, i)
            ])
            seqs.append(feats)
            targs.append([dlat[i], dlon[i]])
            names.append(tr["name"])
    if not seqs:
        return np.zeros((0, SEQ_LEN, 6)), np.zeros((0, 2)), []
    return np.stack(seqs), np.asarray(targs), names


def _rollout(model: NumpyLSTM, points: List[Dict[str, Any]], days: int) -> Tuple[float, float]:
    pts = sorted(points, key=_parse_ts)
    if len(pts) < SEQ_LEN + 1:
        last = pts[-1]
        return last["lat"], last["lon"]
    lat = [p["lat"] for p in pts]
    lon = [p["lon"] for p in pts]
    times = [_parse_ts(p) for p in pts]
    for step in range(days):
        i = len(lat)
        dlat = [0.0] + [lat[k] - lat[k - 1] for k in range(1, i)]
        dlon = [0.0] + [lon[k] - lon[k - 1] for k in range(1, i)]
        feats = np.stack([
            _features_at(lat[k], lon[k], times[k], dlat[k], dlon[k])
            for k in range(i - SEQ_LEN, i)
        ])
        delta = model.predict_delta(feats)
        nlat = lat[-1] + float(delta[0])
        nlon = lon[-1] + float(delta[1])
        lat.append(nlat)
        lon.append(nlon)
        times.append(times[-1] + timedelta(days=1))
    return lat[-1], lon[-1]


def evaluate_split(tracks: List[Dict[str, Any]], holdout_frac=0.15, seed=7) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    usable = [t for t in tracks if track_to_arrays(t["points"]) is not None]
    names = np.array([t["name"] for t in usable])
    n_hold = max(1, int(round(len(usable) * holdout_frac)))
    hold_idx = rng.choice(len(usable), size=n_hold, replace=False)
    hold_set = set(names[hold_idx])
    train = [t for t in usable if t["name"] not in hold_set]
    test = [t for t in usable if t["name"] in hold_set]
    logger.info("LSTM split train_icebergs=%s test_icebergs=%s", len(train), len(test))

    X, y, _ = build_windows(train)
    if len(X) > 4000:
        sel = rng.choice(len(X), 4000, replace=False)
        X, y = X[sel], y[sel]
    field_stats("lstm_train_dlat", y[:, 0] if len(y) else np.array([np.nan]))
    lstm = NumpyLSTM()
    loss_hist = []
    if len(X) >= 32:
        loss_hist = lstm.train(X, y, epochs=8, lr=0.012, batch=64)
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        lstm.save(ARTIFACT_DIR / "lstm_weights.npz")
    else:
        logger.warning("Too few LSTM windows (%s) — weights not trained", len(X))

    baseline = ConstantVelocityModel()
    rows = []
    for tr in test:
        pts = sorted(tr["points"], key=_parse_ts)
        arr = track_to_arrays(pts)
        if arr is None:
            continue
        lat, lon, times = arr["lat"], arr["lon"], arr["t"]
        # walk through the test track: origin at index i, truth at i+h if ~h days later
        for i in range(SEQ_LEN, len(pts) - max(HORIZONS_DAYS) - 1, 11):
            hist = pts[: i + 1]
            for h in HORIZONS_DAYS:
                # find truth ~h days later
                t0d = times[i]
                j = None
                for k in range(i + 1, len(pts)):
                    tkd = times[k]
                    dd = (tkd - t0d).total_seconds() / 86400.0
                    if abs(dd - h) <= 0.6:
                        j = k
                        break
                    if dd > h + 1.5:
                        break
                if j is None:
                    continue
                bpred = baseline.predict_days(hist, [h])[0]
                if len(X) >= 32:
                    plat, plon = _rollout(lstm, hist, h)
                else:
                    plat, plon = bpred["lat"], bpred["lon"]
                ade_b = float(haversine_km(lat[j], lon[j], bpred["lat"], bpred["lon"]))
                ade_m = float(haversine_km(lat[j], lon[j], plat, plon))
                rows.append({"h": h, "baseline_km": ade_b, "lstm_km": ade_m, "name": tr["name"]})

    def agg(h, key):
        vals = [r[key] for r in rows if r["h"] == h]
        return float(np.mean(vals)) if vals else None

    metrics = {
        "n_tracks_total_usable": len(usable),
        "n_train_icebergs": len(train),
        "n_test_icebergs": len(test),
        "holdout_frac": holdout_frac,
        "split": "hold out icebergs (not points within a track)",
        "n_lstm_windows": int(len(X)),
        "lstm_loss_last": float(loss_hist[-1]) if loss_hist else None,
        "n_eval_samples": len(rows),
        "ADE_km": {
            "1d": {"baseline_persistence_velocity": agg(1, "baseline_km"), "lstm": agg(1, "lstm_km")},
            "3d": {"baseline_persistence_velocity": agg(3, "baseline_km"), "lstm": agg(3, "lstm_km")},
            "7d": {"baseline_persistence_velocity": agg(7, "baseline_km"), "lstm": agg(7, "lstm_km")},
        },
        "FDE_km": {
            "note": "Single-horizon displacement; ADE at horizon h equals FDE for that h (one-step-ahead rollout of h days).",
            "1d": agg(1, "lstm_km"),
            "3d": agg(3, "lstm_km"),
            "7d": agg(7, "lstm_km"),
            "baseline_1d": agg(1, "baseline_km"),
            "baseline_3d": agg(3, "baseline_km"),
            "baseline_7d": agg(7, "baseline_km"),
        },
        "units": "km haversine vs actual BYU position on held-out icebergs",
        "trained": bool(len(X) >= 32),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_DIR / "trajectory_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("TRAJECTORY METRICS %s", json.dumps(metrics["ADE_km"]))
    return metrics


class LSTMTrajectoryModel:
    def __init__(self):
        self.model: Optional[NumpyLSTM] = None
        p = ARTIFACT_DIR / "lstm_weights.npz"
        if p.exists():
            try:
                self.model = NumpyLSTM.load(p)
            except Exception as e:
                logger.warning("Could not load LSTM weights: %s", e)

    def predict_days(self, points, days):
        if self.model is None or len(points) < SEQ_LEN:
            return ConstantVelocityModel().predict_days(points, days)
        out = []
        for d in days:
            lat, lon = _rollout(self.model, points, d)
            out.append({"forecast_day": d, "forecast_hour": int(d * 24), "lat": lat, "lon": lon})
        return out


class IcebergTrajectoryPredictor:
    def __init__(self):
        self.lstm = LSTMTrajectoryModel()
        self.baseline = ConstantVelocityModel()
        self.model_status = "LSTM" if self.lstm.model is not None else "PERSISTENCE_VELOCITY"

    def predict(self, iceberg_id, historical_positions, ocean_current=None, wind=None, forecast_hours=None):
        forecast_hours = forecast_hours or [24, 72, 168]
        days = [max(1, int(round(h / 24.0))) for h in forecast_hours]
        if self.lstm.model is not None:
            pred = self.lstm.predict_days(historical_positions, days)
            mtype = "LSTM"
        else:
            pred = self.baseline.predict_days(historical_positions, days)
            mtype = "PERSISTENCE_VELOCITY"
        for p, h in zip(pred, forecast_hours):
            p["forecast_hour"] = h
        metrics_path = ARTIFACT_DIR / "trajectory_metrics.json"
        metrics = None
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        return {
            "predicted_points": pred,
            "confidence_corridor_km": None if not metrics else metrics.get("ADE_km", {}).get("3d", {}).get("lstm"),
            "model_type": mtype,
            "metrics": metrics,
            "note": "Wind/current 2% rule is not used as the reported baseline (no matched multi-decade forcing).",
        }
