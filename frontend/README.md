# 🖥️ IAVNS Frontend (React + Leaflet + Tailwind CSS)

Interactive Web GIS frontend for the **Indian Antarctica Vessels Navigation System (IAVNS)**.

Features a **Google Maps Style 100% Full-Screen Layout** with floating control bars, slide-out drawer menu (`☰`), navigation cards, and downloadable voyage PDF reports.

---

## 🚀 Setup & Execution

### 1. Prerequisites
- **Node.js 18+**
- **npm**

### 2. Installation
```bash
cd frontend
npm install
```

### 3. Running Development Server
```bash
npm run dev
```
The application will run at **`http://localhost:5173/`**.

---

## 🎨 Layout Overview

- 🗺️ **100% Full-Screen Canvas**: `<AntarcticMap>` fills the entire browser window backdrop (`absolute inset-0`).
- 🔍 **Top-Left Floating Header**: IAVNS logo, NCPOR badge, R/V Bharathi status chip, Live API vs Demo mode pill, and `☰` Menu button.
- 📋 **Slide-Out Floating Drawer Menu (`☰`)**:
  - **Layers Tab**: Toggle 9 map layers (Sea Ice, Icebergs, SAR, LSTM Tracks, Risk, Routes, Currents, Weather, Bathymetry).
  - **Route Planner Tab**: Mode selector (**FASTEST**, **SAFEST**, **BALANCED**, **CUSTOM**), custom weights, coordinate pickers, and `⚓ Reset Antarctic Sea Points`.
  - **Vessel Specs Tab**: Configure R/V Bharathi ice class (PC5), draft, speed, and icebreaking capability.
  - **Data & ML Tab**: Live dataset load status and ML model metrics.
- 🚢 **Floating Bottom Navigation Card**:
  - Distance (NM), ETA (h), Fuel (t), Safety Score (%).
  - Expandable **Explainable Risk Breakdown** drawer.
  - **`📥 PDF Report`** export button for printable voyage reports.
- 🧭 **Floating Bottom-Right Map Controls**:
  - Forecast Horizon selector (+24h, +72h, +168h).
  - Basemap Switcher (Full Color OpenStreetMap, Satellite, Voyager, Dark Mode).
  - Live Lat/Lon coordinate hover tracker.

---

## 🔬 Offline Demo Mode

If the backend API is offline or unreachable, the frontend automatically falls back to **Demo Mode** (`demoData.ts` & `useDemoApi.ts`), allowing offline demonstrations with realistic mock data, route computation, and ML metrics.

You can also manually toggle between Live API and Demo Mode using the **`MODE: LIVE API`** pill on the top-left floating bar.

---

## 🛠️ Build for Production
```bash
npm run build
```
Generates production-ready static assets in the `dist/` folder.
