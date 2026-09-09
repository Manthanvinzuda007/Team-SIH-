"""Extent probes for AMSR2 x/y, ICECON flags, SAR GCPs, one iceberg sensor mix."""
from pathlib import Path
import numpy as np
import xarray as xr
import rasterio
from pyproj import Transformer
import pandas as pd

import os
root = Path(os.environ.get("IAVNS_DATA_DIR", "./DataSets"))
f = next((root / "NSIDC _AMSR2_Sea_Ice").glob("*.nc"))
ds = xr.open_dataset(f)
print("x", ds.x.values[:3], "...", ds.x.values[-3:], "min", ds.x.min().item(), "max", ds.x.max().item(), "n", ds.x.size)
print("y", ds.y.values[:3], "...", ds.y.values[-3:], "min", ds.y.min().item(), "max", ds.y.max().item(), "n", ds.y.size)
print("x spacing", np.diff(ds.x.values)[:3], "y spacing", np.diff(ds.y.values)[:3])
ice = ds.ICECON.isel(time=0).values
print("ICECON unique-ish percentiles", np.nanpercentile(ice, [0,1,5,50,95,99,100]))
print("ICECON >1 count", int((ice > 1).sum()), ">1.01", int((ice > 1.01).sum()), "==flags packed?", ice.dtype)

# project x/y EPSG:3412 to 4326
t = Transformer.from_crs("EPSG:3412", "EPSG:4326", always_xy=True)
xx, yy = np.meshgrid(ds.x.values, ds.y.values)
lon, lat = t.transform(xx, yy)
print("AMSR2 lat range", np.nanmin(lat), np.nanmax(lat), "lon", np.nanmin(lon), np.nanmax(lon))
# corners
for name, xi, yi in [("tl", 0, 0), ("tr", -1, 0), ("bl", 0, -1), ("br", -1, -1), ("mid", ds.x.size//2, ds.y.size//2)]:
    lo, la = t.transform(ds.x.values[xi], ds.y.values[yi])
    print(" corner", name, "lon", lo, "lat", la)
ds.close()

safe = root / "Sentinel-1_SAR.SAFE"
tiff = next(safe.rglob("*.tiff"))
with rasterio.open(tiff) as src:
    gcps, crs = src.gcps
    lats = [g.y for g in gcps]
    lons = [g.x for g in gcps]
    print("SAR GCP lat", min(lats), max(lats), "lon", min(lons), max(lons), "n", len(gcps))
    print("SAR first gcp", gcps[0].col, gcps[0].row, gcps[0].x, gcps[0].y)

# iceberg sensors sample
ics = list((root / "Iceberg_Tracking_Database").rglob("*.csv"))
ics = [p for p in ics if "#" not in p.name]
from collections import Counter
sens = Counter()
for p in ics:
    df = pd.read_csv(p, nrows=0)
    for c in df.columns:
        if c.endswith("_1") and c != "size_1":
            sens[c[:-2]] += 1
print("sensor files containing prefix", dict(sens))

# quality flags sample
df = pd.read_csv(ics[0])
print("a01 nic_3 unique", sorted(df.nic_3.dropna().unique())[:20], "sass_3", sorted(df.sass_3.dropna().unique())[:20])
