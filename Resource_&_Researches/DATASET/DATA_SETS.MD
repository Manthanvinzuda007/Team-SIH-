# 🌊 Dataset Analysis

## AI-Enabled Antarctic Sea-Ice, Iceberg Trajectory & Navigation Decision Support System

This document explains the major datasets required for our project.

The datasets are divided into **5 main categories**:

1. 🛰️ Satellite Data
2. 🧊 Sea-Ice Data
3. 🌊 Oceanographic Data
4. 🌦️ Weather & Meteorological Data
5. 🧊 Iceberg Trajectory Data

Our goal is to combine these datasets to build an **AI/ML-based Antarctic navigation decision-support system**.

---

# 1. 🛰️ Satellite Data

Satellite data is one of the most important sources for detecting **sea ice, icebergs, ice edges and ocean conditions**.

## Sentinel-1 SAR

**Type:** C-band Synthetic Aperture Radar (SAR)

| Feature    | Details                                   |
| ---------- | ----------------------------------------- |
| Resolution | ~10 m (ISR mode), 5–20 m in other modes   |
| Coverage   | Global, including Antarctica              |
| Revisit    | ~6–12 days near poles                     |
| Product    | Level-1 GRD / SLC                         |
| Cost       | Free                                      |
| Best Use   | Iceberg detection, sea-ice edge detection |

### Why use it?

Sentinel-1 uses radar, so it can work during:

* 🌙 Night
* ☁️ Cloudy conditions
* ❄️ Polar winter

This makes it extremely useful for Antarctica.

### Limitations

* SAR images contain speckle noise.
* Swath width is limited.
* Processing is more complex than optical imagery.

**Project Importance:** ⭐⭐⭐⭐⭐

---

## Sentinel-2 MSI

**Type:** Optical satellite imagery

| Feature    | Details                               |
| ---------- | ------------------------------------- |
| Resolution | 10 m, 20 m, 60 m depending on band    |
| Revisit    | ~5 days                               |
| Product    | Optical multispectral imagery         |
| Cost       | Free                                  |
| Best Use   | Visual iceberg and sea-ice validation |

### Why use it?

Sentinel-2 provides high-quality optical images that can help us visually confirm:

* Icebergs
* Leads
* Sea-ice boundaries
* Open water

### Limitation

It cannot work properly when:

* ☁️ Clouds are present
* 🌙 There is polar darkness

**Project Importance:** ⭐⭐⭐⭐

---

## Sentinel-3 OLCI / SLSTR

Sentinel-3 is useful for **large-scale ocean and sea-ice monitoring**.

| Instrument |  Resolution | Main Use                    |
| ---------- | ----------: | --------------------------- |
| OLCI       |      ~300 m | Sea-ice/ocean monitoring    |
| SLSTR      | ~500–1000 m | SST and thermal information |

### Uses

* Sea-ice concentration
* Sea Surface Temperature (SST)
* Large-scale ice mapping
* Ocean monitoring

**Project Importance:** ⭐⭐⭐⭐

---

## Sentinel-6 / Jason-CS

**Type:** Satellite Altimetry

It measures **sea-surface height and ice-related elevation/freeboard**.

| Feature                | Details                           |
| ---------------------- | --------------------------------- |
| Along-track resolution | ~7 km                             |
| Repeat                 | ~10 days                          |
| Main Use               | Sea-surface height, ice freeboard |
| Access                 | Free                              |

### Project Use

Can help validate:

* Sea-ice thickness estimates
* Ocean surface conditions
* Ocean circulation information

### Limitation

It is not designed for real-time navigation because of data latency.

**Project Importance:** ⭐⭐⭐

---

## Landsat 8 / 9

**Type:** Optical satellite

| Feature            | Details  |
| ------------------ | -------- |
| VNIR Resolution    | 30 m     |
| Thermal Resolution | 100 m    |
| Revisit            | ~16 days |
| Cost               | Free     |

### Uses

Useful for:

* Detailed iceberg images
* Sea-ice validation
* Studying specific events

### Limitation

Low revisit frequency compared with Sentinel satellites.

**Project Importance:** ⭐⭐⭐

---

## MODIS

Available on NASA's **Terra and Aqua** satellites.

| Feature    | Details   |
| ---------- | --------- |
| Resolution | 250–500 m |
| Frequency  | Daily     |
| Cost       | Free      |

### Uses

* Daily sea-ice monitoring
* Large-scale ice mapping
* Ice-edge monitoring

### Limitation

It is an optical sensor, so clouds and darkness affect observations.

**Project Importance:** ⭐⭐⭐⭐

---

## VIIRS

VIIRS is available on **Suomi NPP and JPSS** satellites.

| Feature    | Details    |
| ---------- | ---------- |
| Resolution | ~375–750 m |
| Frequency  | Daily      |
| Cost       | Free       |

### Uses

Similar to MODIS:

* Sea-ice monitoring
* Ice-edge detection
* Large-scale observation

**Project Importance:** ⭐⭐⭐⭐

---

## ICESat-2

**Type:** Laser Altimeter

ICESat-2 provides highly detailed measurements of the elevation/freeboard of sea ice.

### Uses

* Sea-ice freeboard
* Ice-thickness estimation
* Validation of model predictions

### Limitation

Coverage is sparse compared with imaging satellites.

**Project Importance:** ⭐⭐⭐⭐

---

## CryoSat-2

**Type:** Radar Altimeter

CryoSat-2 is particularly useful for estimating **sea-ice thickness**.

### Uses

* Ice thickness
* Freeboard
* Thickness distribution
* Model validation

**Project Importance:** ⭐⭐⭐⭐

---

## Passive Microwave Sensors

Examples:

* SSMIS
* AMSR2

| Feature        | Details                          |
| -------------- | -------------------------------- |
| Resolution     | ~3–50 km                         |
| Frequency      | Daily                            |
| Main Advantage | Works in most weather conditions |

### Uses

* Sea-ice concentration
* Daily polar ice maps
* Large-scale ice monitoring

### Limitation

Resolution is too coarse for detecting small icebergs.

**Project Importance:** ⭐⭐⭐⭐

---

# 2. 🧊 Sea-Ice Datasets

Sea-ice datasets will be used to understand **where ice exists, how much ice exists and how ice conditions are changing**.

## NSIDC Sea Ice Index

Provides historical sea-ice concentration and extent data.

| Feature             | Details         |
| ------------------- | --------------- |
| Resolution          | ~25 km          |
| Frequency           | Daily / Monthly |
| Historical Coverage | Since 1978      |
| Cost                | Free            |

### Use

Mainly useful for:

* Historical analysis
* Model validation
* Long-term sea-ice trends

### Limitation

Resolution is too coarse for direct ship navigation.

---

## AMSR2 / SSMIS Sea-Ice Concentration

Provides daily polar sea-ice concentration maps.

### Use

Can be used as:

* ML input
* Baseline dataset
* Sea-ice concentration reference

---

## OSI SAF Sea-Ice Concentration

Provides operational European sea-ice products.

### Typical Resolution

~10 km

### Use

* Operational ice monitoring
* Ice concentration
* Ice-edge mapping

---

## Sea-Ice Thickness

Possible sources:

* CryoSat-2
* ESA Climate Change Initiative
* ICESat / ICESat-2

### Why is thickness important?

Two areas may have the same ice concentration but very different navigation risks.

For example:

> 80% thin ice ≠ 80% thick ice.

Therefore, **ice thickness should be included in the navigation risk model whenever possible.**

---

# 3. 🌊 Oceanographic Data

Ocean conditions strongly affect **iceberg movement and sea-ice behaviour**.

## HYCOM Global

**Type:** Ocean model

Provides:

* Ocean currents
* Temperature
* Salinity
* Forecast information

### Resolution

Approximately **1/12°**.

### Project Use

HYCOM can provide ocean-current information to the iceberg trajectory model.

---

## Copernicus Marine / GLORYS

Provides historical ocean analysis and reanalysis.

### Data

* Ocean temperature
* Salinity
* Currents
* Sea-level information

### Project Use

Useful for:

* Training
* Historical simulation
* Validation
* Ocean-current features

---

## Argo Floats

Argo provides measurements of:

* Temperature
* Salinity
* Ocean depth profiles

### Limitation

Argo coverage is relatively sparse in parts of the Southern Ocean.

### Project Use

Useful mainly for validating ocean-model data.

---

## Sea Surface Temperature (SST)

Possible sources:

* NOAA OISST
* GHRSST
* MODIS
* VIIRS
* ERA5

### Project Use

SST can help identify:

* Ocean conditions
* Ice formation/melting environments
* Water-mass characteristics

---

## Bathymetry

Possible sources:

* GEBCO
* IBCSO

### Why is it important?

Bathymetry describes the **depth of the ocean floor**.

It can help identify:

* Shallow areas
* Potential iceberg grounding zones
* Ocean-current patterns

---

## Wave Data

Possible sources:

* ECMWF
* NOAA

Important variables:

* Significant Wave Height (SWH)
* Wave Period
* Wave Direction

### Project Use

Waves affect:

* Ship safety
* Iceberg motion
* Sea-ice breakup

---

# 4. 🌦️ Meteorological / Weather Data

Weather is essential for predicting **iceberg drift and navigation risk**.

## ERA5

One of the most important datasets for our project.

### Resolution

Approximately **31 km**

### Temporal Resolution

Hourly

### Important Variables

* 🌬️ Wind speed
* 🌬️ Wind direction
* 🌡️ Air temperature
* 🧭 Surface pressure
* ☁️ Cloud cover
* 🌧️ Precipitation
* 🧊 Sea-ice-related variables

### Project Use

ERA5 can provide historical weather forcing for:

**Iceberg Trajectory Model**

```text
Wind
  ↓
Ocean Current
  ↓
Iceberg Motion
  ↓
Predicted Trajectory
```

---

## GFS

**Global Forecast System**

Provides forecast information for approximately **0–10 days**.

### Resolution

~0.25°

### Uses

* Future wind
* Temperature
* Pressure
* Weather forecasting

### Project Use

Useful when the system needs **future trajectory prediction** rather than only historical analysis.

---

# 5. 🧊 Iceberg Trajectory Data

This is one of the biggest challenges of the project.

## The Problem

There is **no single comprehensive, freely available Antarctic iceberg trajectory dataset** that contains:

```text
Time
+
Latitude
+
Longitude
+
Iceberg Size
+
Velocity
+
Direction
```

for a large number of icebergs.

Therefore, we cannot depend completely on historical iceberg tracks.

---

# Our Solution

Instead of relying only on historical tracks, we can create a **Physics + AI based trajectory system**.

The model can combine:

```text
                ┌─────────────┐
                │   ERA5      │
                │    Wind     │
                └──────┬──────┘
                       │
                       ↓
┌───────────┐    ┌─────────────┐
│   HYCOM   │ →  │   Iceberg   │
│  Currents │    │    Model    │
└───────────┘    └──────┬──────┘
                       │
┌───────────┐          │
│ Sea Ice   │ ─────────┤
│Concentration│        │
└───────────┘          ↓
                 ┌─────────────┐
                 │ Predicted   │
                 │ Trajectory  │
                 └─────────────┘
```

---

# 6. 🤖 Proposed ML Training Data

Since Antarctic iceberg tracks are limited, we can generate **synthetic training trajectories** using physics-based simulation.

### Inputs

The model can use:

```text
Iceberg Position
Iceberg Size
Iceberg Draft
Wind Speed
Wind Direction
Ocean Current
Sea-Ice Concentration
Sea-Ice Thickness
Wave Height
Sea-Surface Temperature
```

### Output

```text
Future Latitude
Future Longitude
Future Direction
Future Speed
Trajectory
```

---

# 7. 📊 Recommended Dataset Priority

Not every dataset needs to be used in the first version.

## 🔥 High Priority

| Dataset     | Why?                        |
| ----------- | --------------------------- |
| Sentinel-1  | Iceberg + sea-ice detection |
| Sentinel-2  | Visual validation           |
| ERA5        | Wind + weather              |
| HYCOM       | Ocean currents              |
| NSIDC       | Sea-ice concentration       |
| AMSR2/SSMIS | Daily ice concentration     |
| CryoSat-2   | Ice thickness               |
| GEBCO/IBCSO | Ocean depth                 |

---

## 🟡 Medium Priority

| Dataset        | Why?                             |
| -------------- | -------------------------------- |
| Sentinel-3     | Large-scale ice/ocean monitoring |
| MODIS          | Daily monitoring                 |
| VIIRS          | Daily monitoring                 |
| ICESat-2       | Ice thickness validation         |
| GLORYS         | Historical ocean conditions      |
| NOAA OISST     | SST                              |
| Wave Forecasts | Ship/iceberg risk                |

---

## 🟢 Optional / Advanced

| Dataset              | Why?                                    |
| -------------------- | --------------------------------------- |
| Landsat 8/9          | High-detail historical validation       |
| Sentinel-6           | Altimetry                               |
| Argo                 | Ocean validation                        |
| Commercial SAR       | Very high-resolution targeted detection |
| Research cruise data | Ground-truth observations               |

---

# 8. 🧠 How These Datasets Work Together

Our complete data pipeline can look like this:

```text
                  SATELLITE DATA
                       │
       ┌───────────────┼────────────────┐
       ↓               ↓                ↓
 Sentinel-1       Sentinel-2      Sentinel-3
       │               │                │
       └───────────────┼────────────────┘
                       ↓
                ICE DETECTION
                       │
                       ↓
              SEA-ICE DATA
                       │
             ┌─────────┴─────────┐
             ↓                   ↓
       NSIDC / AMSR2        CryoSat-2
       Ice Concentration    Ice Thickness
             │                   │
             └─────────┬─────────┘
                       ↓
                OCEAN DATA
                       │
                ┌──────┴──────┐
                ↓             ↓
              HYCOM         GLORYS
              Currents      Ocean Data
                │             │
                └──────┬──────┘
                       ↓
                WEATHER DATA
                       │
                 ERA5 / GFS
                       │
                       ↓
              ┌─────────────────┐
              │ Iceberg Motion  │
              │     Model       │
              └────────┬────────┘
                       ↓
                AI / ML MODEL
                       ↓
              ┌─────────────────┐
              │ Trajectory      │
              │ Prediction      │
              └────────┬────────┘
                       ↓
              NAVIGATION RISK
                       ↓
             SAFE ROUTE / ALERT
```

---

# 9. 🎯 Final Goal

The final system should answer questions like:

### 🧊 Where is the sea ice?

```text
Sea-Ice Concentration
+
Sea-Ice Thickness
```

### 🛰️ Where are the icebergs?

```text
Sentinel-1
+
Sentinel-2
```

### 🌊 Where will the iceberg move?

```text
Current
+
Wind
+
Waves
+
Sea Ice
+
Physics
+
AI
```

### 🚢 Is the ship route safe?

```text
Iceberg Risk
+
Sea-Ice Risk
+
Weather Risk
+
Wave Risk
+
Bathymetry
        ↓
Navigation Risk Score
```

---

# 10. 🏆 Recommended MVP Dataset Stack

For the **first working prototype**, don't try to integrate everything.

Start with:

### 1️⃣ Sentinel-1

For iceberg / sea-ice detection.

### 2️⃣ NSIDC Sea-Ice Concentration

For historical and current ice concentration.

### 3️⃣ ERA5

For wind and weather.

### 4️⃣ HYCOM

For ocean currents.

### 5️⃣ GEBCO / IBCSO

For bathymetry.

### 6️⃣ CryoSat-2

For ice-thickness information where available.

Then add:

```text
Sentinel-2
      ↓
MODIS / VIIRS
      ↓
GLORYS
      ↓
Wave Data
      ↓
Advanced ML Models
```

---

# 11. ⚠️ Important Data Challenges

### Challenge 1 — Antarctic iceberg tracks

There is no large, clean public dataset of Antarctic iceberg trajectories.

**Solution:** Physics-based simulation + available observations + satellite-derived tracks.

---

### Challenge 2 — Cloud Cover

Optical satellites cannot reliably observe through clouds.

**Solution:** Use Sentinel-1 SAR as the primary detection source.

---

### Challenge 3 — Polar Darkness

Optical imagery is unavailable during polar night.

**Solution:** Use SAR and passive microwave sensors.

---

### Challenge 4 — Different Resolutions

Our datasets have very different resolutions:

```text
Sentinel-1     → ~10 m
Sentinel-2     → ~10 m
Sentinel-3     → ~300 m
AMSR2          → ~10 km
ERA5           → ~31 km
HYCOM          → ~1/12°
NSIDC          → ~25 km
```

**Solution:** Reproject and resample datasets onto a common spatial/temporal grid before ML training.

---

### Challenge 5 — Different Update Frequencies

Some datasets are:

```text
Hourly
Daily
5-day
10-day
Monthly
```

**Solution:** Create a common timeline and interpolate/aggregate data where scientifically appropriate.

---

# 🚀 Final Architecture

```text
DATA SOURCES
     │
     ├── Satellite
     │     ├── Sentinel-1
     │     ├── Sentinel-2
     │     └── Sentinel-3
     │
     ├── Sea Ice
     │     ├── NSIDC
     │     ├── AMSR2
     │     └── CryoSat-2
     │
     ├── Ocean
     │     ├── HYCOM
     │     ├── GLORYS
     │     └── SST
     │
     ├── Weather
     │     ├── ERA5
     │     └── GFS
     │
     └── Geography
           └── GEBCO / IBCSO
              │
              ↓
       DATA PREPROCESSING
              │
              ↓
       FEATURE ENGINEERING
              │
       ┌──────┴─────────┐
       ↓                ↓
 Iceberg Detection   Sea-Ice Forecast
       │                │
       └───────┬────────┘
               ↓
       Iceberg Trajectory
            Prediction
               │
               ↓
        Risk Assessment
               │
               ↓
      Navigation Decision
               │
               ↓
      🚢 SAFE ROUTE / ALERT
```

## ⭐ Key Takeaway

The project should **not depend on one dataset**.

The strongest approach is to combine:

**Satellite + Sea-Ice + Ocean + Weather + Physics + AI**

to create a robust Antarctic navigation decision-support system.

> **Core idea:** Use satellite data to understand **what is happening now**, ocean/weather data to understand **why it is moving**, and physics + AI to predict **what will happen next**.
