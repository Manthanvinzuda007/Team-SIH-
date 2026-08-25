# 🤖 AI/ML Problem Formulation

Our system is divided into **5 main AI/ML tasks**:

## 1. 🧊 Sea-Ice Forecasting

**Goal:** Predict future sea-ice concentration maps.

**Inputs:**

* Previous ice maps
* Wind
* SST

**Model:** ConvLSTM / Transformer

**Output:** Future ice concentration map.

> **Why:** Helps identify areas where ice conditions may become dangerous.

---

## 2. 🛰️ Iceberg Detection

**Goal:** Detect icebergs from satellite images.

**Input:** Sentinel-1 SAR / optical images

**Model:** YOLOv8 / Mask R-CNN

**Output:**

* Iceberg location
* Bounding box / mask

> **Why:** Quickly identifies dangerous icebergs for navigation.

---

## 3. 🧭 Iceberg Trajectory Prediction

**Goal:** Predict where an iceberg will move.

**Inputs:**

* Current position
* Wind
* Ocean currents
* Sea-ice concentration
* Iceberg size

**Model:** LSTM / Transformer + Physics

**Output:** Future iceberg path.

> **Best approach:** Physics gives the basic trajectory, while AI learns and corrects the error.

---

## 4. ⚠️ Navigation Risk Prediction

**Goal:** Calculate how dangerous an area or route is.

Risk depends on:

```text
Sea Ice
+
Iceberg Distance
+
Wind
+
Waves
+
Visibility
        ↓
   Risk Score
```

**Output:**

🟢 Low
🟡 Medium
🟠 High
🔴 Critical

For the MVP, an **explainable rule-based risk score** is preferred; ML can be added later.

---

## 5. 🚢 Route Optimization

**Goal:** Find the safest and most efficient ship route.

The route considers:

* Distance
* Fuel/time
* Ice risk
* Iceberg risk

**Algorithm:** A* (A-Star)

We can generate:

```text
🛡️ Safest Route
⚡ Fastest Route
⚖️ Balanced Route
```

> A* is fast, explainable and practical for the SIH prototype.

---

# 🧠 Why Hybrid AI + Physics?

Antarctic data is limited, so **pure deep learning can overfit**.

Our approach:

```text
Physics Model
     ↓
Initial Prediction
     ↓
     AI
     ↓
Error Correction
     ↓
Better Prediction
```

This hybrid approach is especially useful for **sea-ice forecasting and iceberg drift**.

---

# 🏗️ Simple System Architecture

```text
🛰️ Satellite
🌊 Ocean
🌦️ Weather
🧊 Historical Data
        ↓
  Data Ingestion
        ↓
 Data Cleaning & Fusion
        ↓
    AI / ML Layer
        │
   ┌────┼─────────────┐
   ↓    ↓             ↓
Ice   Iceberg       Iceberg
Forecast Detection  Trajectory
   └────┼─────────────┘
        ↓
   ⚠️ Risk Map
        ↓
   🚢 A* Routing
        ↓
 Recommended Route
        ↓
  🖥️ Web GIS Dashboard
```

The pipeline uses **Antarctic projection EPSG:3031**, a common grid, geospatial storage such as **PostGIS**, and separate ML modules that can run in parallel.

## ⭐ In One Line

> **Detect the ice → predict its movement → calculate risk → find the safest route.**
