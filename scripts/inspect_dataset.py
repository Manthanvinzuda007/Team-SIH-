#!/usr/bin/env python3
"""
POLARIS Antarctic Navigation - Dataset Inspector
Recursively inspects the Dataset directory and produces a detailed inventory.
Classifies datasets by actual content inspection, NOT just filename.
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# Optional imports with graceful fallback
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import netCDF4
    HAS_NETCDF4 = True
except ImportError:
    HAS_NETCDF4 = False

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


DATASET_CATEGORIES = {
    "SENTINEL1_SAR": "Sentinel-1 SAR",
    "NSIDC_AMSR2": "NSIDC / AMSR2 Sea Ice",
    "GLORYS_OCEAN": "GLORYS / Ocean Current",
    "GEBCO_BATHYMETRY": "GEBCO / Bathymetry",
    "ERA5_WEATHER": "ERA5 / Weather",
    "BYU_ICEBERG": "BYU / Iceberg Tracking",
    "DOCUMENTATION": "Documentation",
    "OTHER": "Other Antarctic dataset",
    "UNKNOWN": "Unknown",
}

# Known NetCDF variable signatures for classification
GLORYS_VARIABLES = {"uo", "vo", "thetao", "so", "zos", "mlotst", "bottomT", "siconc"}
ERA5_INSTANT_VARIABLES = {"u10", "v10", "t2m", "sp", "msl", "sst", "d2m", "siconc", "skt", "ci"}
ERA5_ACCUM_VARIABLES = {"tp", "sf", "e", "slhf", "sshf", "ssr", "str", "ssrd", "strd"}
NSIDC_VARIABLES = {"SI_12km_SH_ICECON_DAY", "ICECON", "sea_ice_concentration", "icecon"}
GEBCO_VARIABLES = {"elevation", "z", "Band1"}


def format_size(size_bytes):
    """Format file size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def detect_date_from_filename(filename):
    """Try to extract date from filename patterns."""
    import re
    # YYYYMMDD pattern
    match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 1970 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y}-{m:02d}-{d:02d}"
    # Sentinel-1 datetime pattern
    match = re.search(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}T{match.group(4)}:{match.group(5)}:{match.group(6)}"
    return None


def inspect_netcdf(filepath):
    """Inspect a NetCDF file and return detailed metadata."""
    info = {
        "readable": False,
        "dimensions": {},
        "coordinates": [],
        "variables": {},
        "global_attributes": {},
        "time_info": None,
        "spatial_extent": None,
        "crs": None,
        "missing_values": {},
    }

    if not HAS_NETCDF4:
        info["error"] = "netCDF4 not installed"
        return info

    try:
        ds = netCDF4.Dataset(filepath, "r")
        info["readable"] = True

        # Dimensions
        for dim_name, dim in ds.dimensions.items():
            info["dimensions"][dim_name] = {
                "size": len(dim),
                "unlimited": dim.isunlimited(),
            }

        # Variables
        for var_name, var in ds.variables.items():
            var_info = {
                "dimensions": list(var.dimensions),
                "shape": list(var.shape),
                "dtype": str(var.dtype),
            }
            # Get attributes
            for attr in var.ncattrs():
                try:
                    val = var.getncattr(attr)
                    if isinstance(val, bytes):
                        val = val.decode("utf-8", errors="replace")
                    elif isinstance(val, np.ndarray):
                        val = val.tolist()
                    elif isinstance(val, (np.integer,)):
                        val = int(val)
                    elif isinstance(val, (np.floating,)):
                        val = float(val)
                    var_info[attr] = val
                except Exception:
                    pass
            info["variables"][var_name] = var_info

            # Check for coordinate variables
            if var_name.lower() in ("lat", "latitude", "y", "ygrid"):
                info["coordinates"].append(var_name)
            elif var_name.lower() in ("lon", "longitude", "x", "xgrid"):
                info["coordinates"].append(var_name)
            elif var_name.lower() in ("time", "t"):
                info["coordinates"].append(var_name)

        # Global attributes
        for attr in ds.ncattrs():
            try:
                val = ds.getncattr(attr)
                if isinstance(val, bytes):
                    val = val.decode("utf-8", errors="replace")
                elif isinstance(val, np.ndarray):
                    val = val.tolist()
                elif isinstance(val, (np.integer,)):
                    val = int(val)
                elif isinstance(val, (np.floating,)):
                    val = float(val)
                info["global_attributes"][str(attr)] = val
            except Exception:
                pass

        # Try to extract time info
        for tname in ["time", "t", "Time"]:
            if tname in ds.variables:
                tvar = ds.variables[tname]
                try:
                    units = tvar.getncattr("units") if "units" in tvar.ncattrs() else None
                    calendar = tvar.getncattr("calendar") if "calendar" in tvar.ncattrs() else "standard"
                    tdata = tvar[:]
                    if len(tdata) > 0:
                        info["time_info"] = {
                            "units": units,
                            "calendar": calendar,
                            "num_times": len(tdata),
                            "first_value": float(tdata[0]) if not np.ma.is_masked(tdata[0]) else None,
                            "last_value": float(tdata[-1]) if not np.ma.is_masked(tdata[-1]) else None,
                        }
                        if units and HAS_NETCDF4:
                            try:
                                dates = netCDF4.num2date(tdata, units, calendar)
                                if hasattr(dates, '__len__') and len(dates) > 0:
                                    info["time_info"]["first_date"] = str(dates[0])
                                    info["time_info"]["last_date"] = str(dates[-1])
                            except Exception:
                                pass
                except Exception as e:
                    info["time_info"] = {"error": str(e)}
                break

        # Try to extract spatial extent
        lat_var = None
        lon_var = None
        for name in ["lat", "latitude", "y", "nav_lat"]:
            if name in ds.variables:
                lat_var = ds.variables[name]
                break
        for name in ["lon", "longitude", "x", "nav_lon"]:
            if name in ds.variables:
                lon_var = ds.variables[name]
                break

        if lat_var is not None and lon_var is not None:
            try:
                lats = lat_var[:]
                lons = lon_var[:]
                if HAS_NUMPY:
                    if isinstance(lats, np.ma.MaskedArray):
                        lats = lats.compressed()
                    if isinstance(lons, np.ma.MaskedArray):
                        lons = lons.compressed()
                    if len(lats) > 0 and len(lons) > 0:
                        info["spatial_extent"] = {
                            "lat_min": float(np.nanmin(lats)),
                            "lat_max": float(np.nanmax(lats)),
                            "lon_min": float(np.nanmin(lons)),
                            "lon_max": float(np.nanmax(lons)),
                        }
            except Exception:
                pass

        # CRS info
        for attr_name in ["crs", "projection", "grid_mapping", "spatial_ref"]:
            if attr_name in ds.variables:
                crs_var = ds.variables[attr_name]
                crs_info = {}
                for a in crs_var.ncattrs():
                    try:
                        crs_info[a] = str(crs_var.getncattr(a))
                    except Exception:
                        pass
                info["crs"] = crs_info
                break
        
        # Check global attrs for CRS
        if info["crs"] is None:
            for attr_name in ["projection", "crs_wkt", "spatial_ref"]:
                if attr_name in info["global_attributes"]:
                    info["crs"] = info["global_attributes"][attr_name]
                    break

        ds.close()

    except Exception as e:
        info["error"] = str(e)

    return info


def inspect_geotiff(filepath):
    """Inspect a GeoTIFF file."""
    info = {"readable": False}

    if not HAS_RASTERIO:
        info["error"] = "rasterio not installed"
        return info

    try:
        with rasterio.open(filepath) as ds:
            info["readable"] = True
            info["crs"] = str(ds.crs) if ds.crs else None
            info["bounds"] = {
                "left": ds.bounds.left,
                "bottom": ds.bounds.bottom,
                "right": ds.bounds.right,
                "top": ds.bounds.top,
            }
            info["width"] = ds.width
            info["height"] = ds.height
            info["count"] = ds.count
            info["dtypes"] = list(ds.dtypes)
            info["transform"] = list(ds.transform)[:6]
            info["nodata"] = ds.nodata
            info["driver"] = ds.driver
            # Resolution
            info["resolution"] = {
                "x": abs(ds.transform[0]),
                "y": abs(ds.transform[4]),
            }
    except Exception as e:
        info["error"] = str(e)

    return info


def inspect_csv(filepath, max_rows=5):
    """Inspect a CSV file."""
    info = {"readable": False}

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        info["readable"] = True
        info["num_lines"] = len(lines)

        if len(lines) > 0:
            info["header"] = lines[0].strip()
            info["columns"] = [c.strip() for c in lines[0].strip().split(",")]
            info["num_columns"] = len(info["columns"])

        if len(lines) > 1:
            info["sample_rows"] = [l.strip() for l in lines[1:min(max_rows+1, len(lines))]]

        # Detect if it's iceberg tracking data
        if info.get("columns"):
            cols = set(c.lower() for c in info["columns"])
            if "date" in cols and any("_1" in c for c in info["columns"]):
                info["detected_type"] = "BYU_ICEBERG_TRACK"
                # Try to get date range
                if HAS_PANDAS:
                    try:
                        df = pd.read_csv(filepath)
                        if "date" in df.columns:
                            dates = df["date"].dropna()
                            if len(dates) > 0:
                                info["date_range"] = {
                                    "first": int(dates.iloc[0]),
                                    "last": int(dates.iloc[-1]),
                                    "num_records": len(dates),
                                }
                                # Convert YYYYDDD to readable
                                try:
                                    first_year = int(str(int(dates.iloc[0]))[:4])
                                    first_doy = int(str(int(dates.iloc[0]))[4:])
                                    last_year = int(str(int(dates.iloc[-1]))[:4])
                                    last_doy = int(str(int(dates.iloc[-1]))[4:])
                                    from datetime import date
                                    first_date = date(first_year, 1, 1) + __import__('datetime').timedelta(days=first_doy - 1)
                                    last_date = date(last_year, 1, 1) + __import__('datetime').timedelta(days=last_doy - 1)
                                    info["date_range"]["first_readable"] = str(first_date)
                                    info["date_range"]["last_readable"] = str(last_date)
                                except Exception:
                                    pass

                            # Find sensor columns
                            sensors = set()
                            for col in df.columns:
                                if col.endswith("_1"):
                                    sensors.add(col[:-2])
                            info["sensors"] = sorted(list(sensors))

                            # Count valid positions
                            valid_count = 0
                            for sensor in sensors:
                                lat_col = f"{sensor}_1"
                                lon_col = f"{sensor}_2"
                                if lat_col in df.columns and lon_col in df.columns:
                                    valid = df[(df[lat_col] != 0) & (df[lon_col] != 0)]
                                    valid_count += len(valid)
                            info["valid_position_count"] = valid_count
                    except Exception:
                        pass

    except Exception as e:
        info["error"] = str(e)

    return info


def classify_dataset(filepath, file_info):
    """Classify a dataset based on content inspection, not just filename."""
    name = os.path.basename(filepath).lower()
    ext = os.path.splitext(name)[1]
    parent_dir = os.path.basename(os.path.dirname(filepath)).lower()

    # PDF documentation
    if ext == ".pdf":
        return "DOCUMENTATION", "PDF document"

    # XML - annotation/metadata
    if ext == ".xml":
        if "safe" in str(filepath).lower() or "annotation" in str(filepath).lower():
            return "SENTINEL1_SAR", "SAR annotation XML"
        return "OTHER", "XML metadata"

    # SAFE manifest
    if name == "manifest.safe":
        return "SENTINEL1_SAR", "Sentinel-1 SAFE manifest"

    # GeoTIFF in SAR directory
    if ext in (".tiff", ".tif"):
        if "s1" in name or "safe" in str(filepath).lower():
            return "SENTINEL1_SAR", "SAR measurement GeoTIFF"
        return "OTHER", "GeoTIFF raster"

    # CSV files
    if ext == ".csv":
        if file_info.get("detected_type") == "BYU_ICEBERG_TRACK":
            return "BYU_ICEBERG", "Iceberg tracking data"
        if parent_dir == "updated7_consol":
            return "BYU_ICEBERG", "Likely iceberg tracking data (in BYU directory)"
        return "UNKNOWN", "CSV file - content not matched"

    # TXT files
    if ext == ".txt":
        if "readme" in name:
            return "DOCUMENTATION", "README documentation"
        return "OTHER", "Text file"

    # NetCDF files - classify by variable inspection
    if ext == ".nc":
        nc_info = file_info.get("netcdf", {})
        variables = set(nc_info.get("variables", {}).keys())

        # Check GLORYS/CMEMS ocean variables
        if variables & GLORYS_VARIABLES:
            matched = variables & GLORYS_VARIABLES
            return "GLORYS_OCEAN", f"GLORYS/CMEMS ocean data (matched vars: {', '.join(sorted(matched))})"

        # Check ERA5 instantaneous variables
        if variables & ERA5_INSTANT_VARIABLES:
            matched = variables & ERA5_INSTANT_VARIABLES
            return "ERA5_WEATHER", f"ERA5 instantaneous weather data (matched vars: {', '.join(sorted(matched))})"

        # Check ERA5 accumulated variables
        if variables & ERA5_ACCUM_VARIABLES:
            matched = variables & ERA5_ACCUM_VARIABLES
            return "ERA5_WEATHER", f"ERA5 accumulated weather data (matched vars: {', '.join(sorted(matched))})"

        # Check NSIDC sea ice variables
        if variables & NSIDC_VARIABLES:
            matched = variables & NSIDC_VARIABLES
            return "NSIDC_AMSR2", f"NSIDC/AMSR2 sea ice data (matched vars: {', '.join(sorted(matched))})"

        # Check GEBCO bathymetry
        if variables & GEBCO_VARIABLES:
            matched = variables & GEBCO_VARIABLES
            return "GEBCO_BATHYMETRY", f"GEBCO bathymetry (matched vars: {', '.join(sorted(matched))})"

        # Check by global attributes
        global_attrs = nc_info.get("global_attributes", {})
        source = str(global_attrs.get("source", "")).lower()
        title = str(global_attrs.get("title", "")).lower()
        institution = str(global_attrs.get("institution", "")).lower()

        if "nsidc" in source or "amsr" in title or "sea ice" in title:
            return "NSIDC_AMSR2", f"NSIDC data (from attributes)"
        if "cmems" in source or "glorys" in title or "mercator" in institution:
            return "GLORYS_OCEAN", f"GLORYS/CMEMS data (from attributes)"
        if "gebco" in source or "gebco" in title or "bathymetry" in title:
            return "GEBCO_BATHYMETRY", f"GEBCO data (from attributes)"
        if "ecmwf" in source or "era5" in title or "era5" in source:
            return "ERA5_WEATHER", f"ERA5 data (from attributes)"

        # Check by filename as last resort
        if "nsidc" in name or "amsr" in name or "seaice" in name:
            return "NSIDC_AMSR2", f"Likely NSIDC (from filename, variables: {', '.join(sorted(variables))})"
        if "cmems" in name or "glorys" in name or "glo_phy" in name:
            return "GLORYS_OCEAN", f"Likely GLORYS (from filename, variables: {', '.join(sorted(variables))})"
        if "gebco" in name:
            return "GEBCO_BATHYMETRY", f"Likely GEBCO (from filename, variables: {', '.join(sorted(variables))})"

        # Check spatial extent for Antarctic data
        spatial = nc_info.get("spatial_extent", {})
        if spatial:
            lat_min = spatial.get("lat_min", 0)
            if lat_min < -50:
                return "OTHER", f"Antarctic NetCDF data (vars: {', '.join(sorted(variables))})"

        return "UNKNOWN", f"Unclassified NetCDF (variables: {', '.join(sorted(variables))})"

    return "UNKNOWN", f"Unknown file type: {ext}"


def inspect_directory(dataset_path):
    """Recursively inspect the dataset directory."""
    print(f"\n{'='*70}")
    print(f"  POLARIS Dataset Inspector")
    print(f"  Inspecting: {dataset_path}")
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*70}\n")

    inventory = {
        "inspection_time": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "python_packages": {
            "numpy": HAS_NUMPY,
            "netCDF4": HAS_NETCDF4,
            "xarray": HAS_XARRAY,
            "rasterio": HAS_RASTERIO,
            "pandas": HAS_PANDAS,
        },
        "summary": {
            "total_files": 0,
            "total_size_bytes": 0,
            "total_directories": 0,
            "by_extension": defaultdict(int),
            "by_category": defaultdict(int),
        },
        "datasets": [],
        "updated7_consol_summary": None,
        "warnings": [],
    }

    all_files = []
    for root, dirs, files in os.walk(dataset_path):
        inventory["summary"]["total_directories"] += len(dirs)
        for fname in files:
            fpath = os.path.join(root, fname)
            all_files.append(fpath)

    inventory["summary"]["total_files"] = len(all_files)
    print(f"Found {len(all_files)} files in {inventory['summary']['total_directories']} directories\n")

    # Track iceberg files separately for summary
    iceberg_files_info = []

    for i, fpath in enumerate(sorted(all_files)):
        fname = os.path.basename(fpath)
        ext = os.path.splitext(fname)[1].lower()
        rel_path = os.path.relpath(fpath, dataset_path)
        size = os.path.getsize(fpath)

        inventory["summary"]["total_size_bytes"] += size
        inventory["summary"]["by_extension"][ext] += 1

        file_entry = {
            "path": rel_path,
            "filename": fname,
            "extension": ext,
            "size_bytes": size,
            "size_human": format_size(size),
            "date_detected": detect_date_from_filename(fname),
        }

        # Inspect based on type
        if ext == ".nc":
            print(f"  [{i+1}/{len(all_files)}] Inspecting NetCDF: {rel_path} ({format_size(size)})")
            nc_info = inspect_netcdf(fpath)
            file_entry["netcdf"] = nc_info
            file_entry["readable"] = nc_info.get("readable", False)

        elif ext in (".tiff", ".tif"):
            print(f"  [{i+1}/{len(all_files)}] Inspecting GeoTIFF: {rel_path} ({format_size(size)})")
            tiff_info = inspect_geotiff(fpath)
            file_entry["geotiff"] = tiff_info
            file_entry["readable"] = tiff_info.get("readable", False)

        elif ext == ".csv":
            # Only print for non-bulk iceberg files
            parent = os.path.basename(os.path.dirname(fpath))
            if parent == "updated7_consol":
                file_entry["readable"] = True
                csv_info = inspect_csv(fpath)
                file_entry["csv"] = csv_info
                iceberg_files_info.append(file_entry)
                if i % 50 == 0:
                    print(f"  [{i+1}/{len(all_files)}] Inspecting iceberg CSVs... ({fname})")
            else:
                print(f"  [{i+1}/{len(all_files)}] Inspecting CSV: {rel_path}")
                csv_info = inspect_csv(fpath)
                file_entry["csv"] = csv_info
                file_entry["readable"] = csv_info.get("readable", False)

        elif ext in (".pdf",):
            print(f"  [{i+1}/{len(all_files)}] Documentation: {rel_path}")
            file_entry["readable"] = True

        elif ext in (".xml", ".safe", ".xsd", ".html"):
            print(f"  [{i+1}/{len(all_files)}] Metadata: {rel_path}")
            file_entry["readable"] = True

        else:
            print(f"  [{i+1}/{len(all_files)}] Other: {rel_path} ({format_size(size)})")
            file_entry["readable"] = True

        # Classify
        category, reason = classify_dataset(fpath, file_entry)
        file_entry["category"] = category
        file_entry["category_label"] = DATASET_CATEGORIES.get(category, category)
        file_entry["classification_reason"] = reason

        inventory["summary"]["by_category"][category] += 1
        inventory["datasets"].append(file_entry)

    # Generate updated7_consol summary
    if iceberg_files_info:
        print(f"\n  Processing iceberg database summary ({len(iceberg_files_info)} files)...")
        all_sensors = set()
        total_records = 0
        date_min = None
        date_max = None
        total_valid_positions = 0

        for entry in iceberg_files_info:
            csv = entry.get("csv", {})
            if "sensors" in csv:
                all_sensors.update(csv["sensors"])
            if "date_range" in csv:
                dr = csv["date_range"]
                if date_min is None or dr.get("first", 9999999) < date_min:
                    date_min = dr.get("first")
                if date_max is None or dr.get("last", 0) > date_max:
                    date_max = dr.get("last")
                total_records += dr.get("num_records", 0)
            total_valid_positions += csv.get("valid_position_count", 0)

        # Convert date bounds
        date_min_readable = None
        date_max_readable = None
        if date_min:
            try:
                from datetime import date, timedelta
                y = int(str(date_min)[:4])
                d = int(str(date_min)[4:])
                date_min_readable = str(date(y, 1, 1) + timedelta(days=d - 1))
            except Exception:
                pass
        if date_max:
            try:
                from datetime import date, timedelta
                y = int(str(date_max)[:4])
                d = int(str(date_max)[4:])
                date_max_readable = str(date(y, 1, 1) + timedelta(days=d - 1))
            except Exception:
                pass

        inventory["updated7_consol_summary"] = {
            "detected_type": "BYU MERS Consolidated Antarctic Iceberg Tracking Database",
            "total_files": len(iceberg_files_info),
            "total_size_bytes": sum(e["size_bytes"] for e in iceberg_files_info),
            "total_size_human": format_size(sum(e["size_bytes"] for e in iceberg_files_info)),
            "total_records": total_records,
            "total_valid_positions": total_valid_positions,
            "sensors_found": sorted(list(all_sensors)),
            "date_range": {
                "first_julian": date_min,
                "last_julian": date_max,
                "first_readable": date_min_readable,
                "last_readable": date_max_readable,
            },
            "naming_convention": "a=quadrant A, b=quadrant B, c=quadrant C, d=quadrant D, e=ERS, sa=SASS, uk=unnamed",
            "usage_in_system": "Iceberg trajectory ground truth, historical drift patterns, trajectory model training",
        }

    # Print summary
    print(f"\n{'='*70}")
    print(f"  DATASET INVENTORY SUMMARY")
    print(f"{'='*70}")
    print(f"  Total files: {inventory['summary']['total_files']}")
    print(f"  Total size: {format_size(inventory['summary']['total_size_bytes'])}")
    print(f"  Directories: {inventory['summary']['total_directories']}")
    print(f"\n  By Extension:")
    for ext, count in sorted(inventory["summary"]["by_extension"].items()):
        print(f"    {ext or '(none)'}: {count}")
    print(f"\n  By Category:")
    for cat, count in sorted(inventory["summary"]["by_category"].items()):
        print(f"    {DATASET_CATEGORIES.get(cat, cat)}: {count}")

    # Print NetCDF details
    print(f"\n{'='*70}")
    print(f"  NETCDF FILE DETAILS")
    print(f"{'='*70}")
    for entry in inventory["datasets"]:
        if entry["extension"] == ".nc":
            nc = entry.get("netcdf", {})
            print(f"\n  File: {entry['path']}")
            print(f"  Size: {entry['size_human']}")
            print(f"  Category: {entry['category_label']}")
            print(f"  Reason: {entry['classification_reason']}")
            print(f"  Readable: {nc.get('readable', False)}")
            if nc.get("readable"):
                print(f"  Dimensions: {nc.get('dimensions', {})}")
                print(f"  Variables: {list(nc.get('variables', {}).keys())}")
                if nc.get("time_info"):
                    print(f"  Time: {nc['time_info']}")
                if nc.get("spatial_extent"):
                    print(f"  Spatial: {nc['spatial_extent']}")
                if nc.get("crs"):
                    print(f"  CRS: {nc['crs']}")

    # Print updated7_consol summary
    if inventory["updated7_consol_summary"]:
        summary = inventory["updated7_consol_summary"]
        print(f"\n{'='*70}")
        print(f"  UPDATED7_CONSOL ANALYSIS")
        print(f"{'='*70}")
        print(f"  Detected type: {summary['detected_type']}")
        print(f"  Files: {summary['total_files']}")
        print(f"  Total size: {summary['total_size_human']}")
        print(f"  Total records: {summary['total_records']}")
        print(f"  Valid positions: {summary['total_valid_positions']}")
        print(f"  Sensors: {summary['sensors_found']}")
        print(f"  Date range: {summary['date_range']['first_readable']} to {summary['date_range']['last_readable']}")
        print(f"  Usage: {summary['usage_in_system']}")

    # Convert defaultdicts to regular dicts for JSON serialization
    inventory["summary"]["by_extension"] = dict(inventory["summary"]["by_extension"])
    inventory["summary"]["by_category"] = dict(inventory["summary"]["by_category"])

    return inventory


def main():
    # Determine dataset path
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    dataset_path = project_root.parent / "DataSets"

    if not dataset_path.exists():
        # Try alternative paths
        import os
        env_dir = os.environ.get("IAVNS_DATA_DIR")
        candidates = ([Path(env_dir)] if env_dir else []) + [Path("Dataset"), Path("../Dataset")]
        for alt in candidates:
            if alt.exists():
                dataset_path = alt
                break

    if not dataset_path.exists():
        print(f"ERROR: Dataset directory not found at {dataset_path}")
        sys.exit(1)

    print(f"Dataset path: {dataset_path}")

    # Run inspection
    inventory = inspect_directory(str(dataset_path))

    # Save JSON report
    output_path = script_dir / "dataset_inventory.json"
    
    # Custom JSON encoder for non-serializable types
    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (set, frozenset)):
                return list(obj)
            if isinstance(obj, Path):
                return str(obj)
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            try:
                return float(obj)
            except (TypeError, ValueError):
                return str(obj)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, cls=CustomEncoder, default=str)

    print(f"\n  Inventory saved to: {output_path}")
    print(f"\n{'='*70}")
    print(f"  INSPECTION COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
