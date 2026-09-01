"""One-shot content inspection of real dataset files. Not a source of fabricated names."""
from pathlib import Path
import numpy as np
import xarray as xr
import rasterio
import pandas as pd

import os
root = Path(os.environ.get("IAVNS_DATA_DIR", "./DataSets"))
print("ROOT", root, "exists", root.exists())

amsr = list((root / "NSIDC _AMSR2_Sea_Ice").glob("*.nc"))
print("\n=== AMSR2 n=", len(amsr))
if amsr:
    ds = xr.open_dataset(amsr[0])
    print("file", amsr[0].name)
    print("dims", dict(ds.dims))
    print("coords", list(ds.coords))
    print("data_vars", {k: (ds[k].dims, ds[k].shape, str(ds[k].dtype)) for k in ds.data_vars})
    for k in ds.data_vars:
        a = ds[k]
        print(" VAR", k, "attrs", dict(list(a.attrs.items())[:12]))
        try:
            v = np.asarray(a.values)
            finite = np.isfinite(v) if np.issubdtype(v.dtype, np.floating) else np.ones_like(v, dtype=bool)
            print("  min/max/nanfrac", np.nanmin(v), np.nanmax(v), 1.0 - finite.mean())
        except Exception as e:
            print("  stats err", e)
    print("global attrs keys", list(ds.attrs)[:30])
    ds.close()

glorys = list((root / "GLORYS_Ocean_Current_Data").glob("*.nc"))
print("\n=== GLORYS n=", len(glorys), glorys[0].name if glorys else None)
if glorys:
    ds = xr.open_dataset(glorys[0])
    print("dims", dict(ds.dims))
    print("coords", list(ds.coords))
    print("data_vars", {k: (ds[k].dims, ds[k].shape) for k in ds.data_vars})
    for c in ds.coords:
        try:
            arr = ds[c].values
            print(" coord", c, arr.shape, "min", np.nanmin(arr), "max", np.nanmax(arr))
        except Exception as e:
            print(" coord", c, e)
    ds.close()

gebco = list((root / "GEBCO_Dataset").glob("*.nc"))
print("\n=== GEBCO n=", len(gebco), gebco[0].name if gebco else None)
if gebco:
    ds = xr.open_dataset(gebco[0], decode_times=False)
    print("dims", dict(ds.dims))
    print("vars", list(ds.variables))
    for name in ["lat", "latitude", "lon", "longitude", "x", "y"]:
        if name in ds.variables:
            a = ds[name].values
            print(name, a.shape, float(a.min()), float(a.max()), a[:3], a[-3:])
    ds.close()

era = list((root / "ERA5_Dtaset").rglob("*.nc"))
print("\n=== ERA5 n=", len(era))
for f in era:
    ds = xr.open_dataset(f)
    print(f.name)
    print(" dims", dict(ds.dims))
    print(" vars", {k: (ds[k].dims, ds[k].shape) for k in list(ds.coords) + list(ds.data_vars)})
    for c in ["latitude", "longitude", "lat", "lon", "valid_time", "time"]:
        if c in ds:
            a = ds[c].values
            if np.issubdtype(a.dtype, np.number):
                print(" ", c, a.shape, a.min(), a.max())
            else:
                print(" ", c, a.shape, a[0], a[-1])
    ds.close()

safe = root / "Sentinel-1_SAR.SAFE"
print("\n=== SAR exists", safe.exists())
tiffs = list(safe.rglob("*.tiff")) + list(safe.rglob("*.tif"))
print("tiffs", [str(t.relative_to(safe)) for t in tiffs])
cals = list(safe.rglob("calibration-*.xml"))
noises = list(safe.rglob("noise-*.xml"))
print("cals", [c.name for c in cals], "noises", [n.name for n in noises])
if tiffs:
    with rasterio.open(tiffs[0]) as src:
        print("width", src.width, "height", src.height, "crs", src.crs, "count", src.count, "dtype", src.dtypes)
        print("bounds", src.bounds)
        print("transform", src.transform)
        gcp_pts, gcp_crs = src.gcps
        print("gcps", len(gcp_pts), "gcp_crs", gcp_crs)
        w = min(64, src.width)
        h = min(64, src.height)
        a = src.read(1, window=rasterio.windows.Window(0, 0, w, h))
        print("window sample min/max/mean", int(a.min()), int(a.max()), float(a.mean()))

ics = root / "Iceberg_Tracking_Database"
csvs = [p for p in ics.rglob("*.csv") if "#" not in p.name]
print("\n=== ICEBERG csv n=", len(csvs))
pref_all = set()
nfiles = 0
nbad = 0
for p in csvs:
    try:
        df = pd.read_csv(p, nrows=1)
        nfiles += 1
        for c in df.columns:
            if c.endswith("_1") and c != "size_1":
                pref_all.add(c[:-2])
    except Exception:
        nbad += 1
print("all prefixes", pref_all, "nfiles", nfiles, "nbad", nbad)
df = pd.read_csv(csvs[0])
print("example file", csvs[0].name, "shape", df.shape, "cols", list(df.columns))
print(df.head(3).to_string())
