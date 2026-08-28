"""Live data-status from files on disk + last loader stats (not a one-shot JSON cache)."""
from __future__ import annotations

import os
from datetime import datetime

from app.core.config import get_settings
from app.core.pipeline import get_loaders


class DataStatusService:
    def get_all_status(self):
        root = str(get_settings().dataset_dir)
        loaders = get_loaders()
        datasets = []
        for key, loader in loaders.items():
            prov = loader.get_provenance()
            files = getattr(loader, "files", []) or []
            sizes = []
            mtimes = []
            for f in files:
                try:
                    if os.path.isdir(f):
                        for dp, _, fnames in os.walk(f):
                            for n in fnames:
                                p = os.path.join(dp, n)
                                sizes.append(os.path.getsize(p))
                                mtimes.append(os.path.getmtime(p))
                    else:
                        sizes.append(os.path.getsize(f))
                        mtimes.append(os.path.getmtime(f))
                except OSError:
                    pass
            last = max(mtimes) if mtimes else None
            age_h = (datetime.utcnow().timestamp() - last) / 3600.0 if last else None
            prov["files_found"] = len(files)
            prov["bytes_on_disk"] = int(sum(sizes))
            prov["last_updated"] = datetime.utcfromtimestamp(last).isoformat() + "Z" if last else None
            prov["data_age_hours"] = round(age_h, 1) if age_h is not None else None
            prov["dataset_root"] = root
            prov["freshness_note"] = (
                "Static historical files on disk — this prototype does not ingest live satellite feeds. "
                "data_age_hours is wall-clock age of the file mtime, not an operational latency SLA."
            )
            datasets.append(prov)
        return {
            "datasets": datasets,
            "dataset_root": root,
            "demo_window": "Sea ice + ERA5: 2026-08-01..08. GLORYS: 2026-06-01..08 mean. SAR: 2026-08-22. BYU: multi-decade.",
        }
