# ⚓ INDIAN ANTARCTICA VESSELS NAVIGATION SYSTEM (IAVNS)

> **AI/ML-Enabled Decision Support Platform for Antarctic Sea-Ice Forecasting, Iceberg Trajectory Prediction & Vessel-Aware Route Optimization**  
> *Developed for NCPOR (National Centre for Polar and Ocean Research), MoES & ISRO (SIH PS-26059)*

---

## 🌟 Overview & Features

IAVNS is an end-to-end polar navigation decision support platform designed to assist research vessels (such as **R/V Bharathi**) navigating through the harsh conditions of the Southern Ocean and Antarctic Peninsula.

### Key Innovations & Features:
- 🗺️ **Google Maps Style 100% Full-Screen UI**: Viewport-wide interactive map backdrop with floating glass control bars, slide-out drawer menu (`☰`), and navigation cards.
- 🚢 **NCPOR R/V Bharathi Vessel Profile**: Pre-configured for PC5 Ice Class, 6.15 m draft, 15 knot max speed, and icebreaking capability.
- ⚡ **Multi-Waypoint Safe Route Optimization**: A* pathfinding algorithm on EPSG:3031 grid generating 110+ curved waypoints across **FASTEST**, **SAFEST**, **BALANCED**, and **CUSTOM** route modes.
- ⚓ **Open-Water Cell Snapping**: Automatic coastal point snapping (`_find_nearest_unblocked_cell`) ensures valid paths without land fallbacks.
- 🌐 **Global Earth Extent Heatmaps**: Seamless 360° global coverage for **ERA5 Wind Speed Weather** and **GLORYS Ocean Current Vectors**.
- 🧠 **Multi-Model ML Pipeline**:
  - **Iceberg Drift Prediction**: PyTorch/Numpy LSTM model trained on 530+ BYU tracks (ADE 14.2 km @ 24h).
  - **Sea-Ice Forecasting**: Optical Flow Advection Nowcaster on AMSR2 25 km passive microwave grids.
  - **SAR Target Detector**: CFAR + YOLOv8 candidate detection on Sentinel-1 radar scenes.
- 🛡️ **Explainable Risk Breakdown**: Per-component hazard scores for Sea Ice, Icebergs, Weather, Bathymetry, and Ocean Currents.
- 📄 **Downloadable Voyage PDF Report**: One-click export for official NCPOR/MoES expedition voyage reports.
- 🔬 **Dual Live API & Offline Demo Mode**: Seamless fallback mode (`demoData.ts`) if backend API is unreachable.

---

## 🏗️ System Architecture

```
                               ┌────────────────────────────────────────────────┐
                               │   Copernicus / NASA / NSIDC Data Ingestion     │
                               │ (Sentinel-1 SAR, AMSR2, ERA5, GLORYS, GEBCO)  │
                               └───────────────────────┬────────────────────────┘
                                                       │
                                                       ▼
                               ┌────────────────────────────────────────────────┐
                               │       FastAPI Python Backend (Port 8000)        │
                               │ ┌────────────────────────────────────────────┐ │
                               │ │ - Analysis Grid (EPSG:3031 @ 10 km)        │ │
                               │ │ - LSTM Iceberg Trajectory Predictor        │ │
                               │ │ - Sea-Ice Optical Flow Nowcaster           │ │
                               │ │ - A* Multi-Objective Route Optimizer       │ │
                               │ └────────────────────────────────────────────┘ │
                               └───────────────────────┬────────────────────────┘
                                                       │
                                                       ▼ REST API / JSON
                               ┌────────────────────────────────────────────────┐
                               │      React 18 + Leaflet Frontend (Port 5173)   │
                               │ (Google Maps Full-Screen UI, Floating Drawer)  │
                               └────────────────────────────────────────────────┘
```

---

## ⚙️ Prerequisites

Ensure you have the following installed on your system:
- **Python 3.11+** (Python 3.11 or 3.12 recommended)
- **uv** (Fast Python package manager) or standard `venv`
- **Node.js 18+** & **npm**

---

## 🚀 Quickstart Guide (Step-by-Step)

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-repo/antarctic-navigation.git
cd antarctic-navigation
```

---

### Step 2: Start the FastAPI Backend

1. **Navigate to the `backend` folder**:
   ```bash
   cd backend
   ```

2. **Set up Python Virtual Environment & Install Dependencies**:
   - **Default (Fastest & Recommended with `uv`)**:
     ```bash
     uv sync
     ```
     *(This creates `.venv` and installs all packages from `pyproject.toml` in seconds.)*

3. **Activate the Virtual Environment & Populate Database**:
   ```bash
   # Windows (PowerShell)
   .\.venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate

   # Seed database (run once)
   python scripts/populate_db.py
   ```

4. **Start the API Server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Configure Environment Variables**:
   Ensure `backend/.env` exists (or copy `.env.example`):
   ```ini
   APP_NAME="IAVNS Antarctic Navigation"
   IAVNS_DATA_DIR=./DataSets
   DATABASE_URL=sqlite:///./iavns.db
   CORS_ORIGINS=["http://localhost:5173","http://localhost:5174"]
   ```

4. **Populate Historical Database (Run Once)**:
   ```bash
   python scripts/populate_db.py
   ```

5. **Start the FastAPI Server**:
   ```bash
   # Windows
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

   # macOS / Linux
   .venv/bin/python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
   ```
   - **Backend API**: Running at [http://localhost:8000](http://localhost:8000)
   - **Interactive API Documentation (Swagger)**: Available at [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Step 3: Start the React Frontend

1. **Open a new terminal window** and navigate to the `frontend` folder:
   ```bash
   cd antarctic-navigation/frontend
   ```

2. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

3. **Start the Vite Development Server**:
   ```bash
   npm run dev
   ```

4. **Open in Browser**:
   Navigate to **[http://localhost:5173](http://localhost:5173)** in your browser!

---

## 🎮 How to Use IAVNS

1. **Explore the Map**:
   - Use the **Basemap Switcher** (top-left inside drawer or map controls) to toggle between **Full Color OpenStreetMap**, **Esri Satellite**, **Carto Voyager**, and **Dark Mode**.
2. **Open the Drawer Menu (`☰`)**:
   - Click the `☰` button on the top-left floating bar to open the side drawer.
   - **Layers Tab**: Toggle Sea Ice, BYU Icebergs, SAR Detections, LSTM Trajectories, Risk Map, Weather, Currents, and Bathymetry.
   - **Route Planner Tab**: Select route mode (**FASTEST**, **SAFEST**, **BALANCED**, **CUSTOM**), pick coordinates, or click **`⚓ Reset Antarctic Sea Points`**.
   - **Vessel Specs Tab**: Customize vessel parameters for **R/V Bharathi**.
3. **Compute Route**:
   - Click **`▶ Compute BALANCED Route`** on the bottom navigation card.
   - View distance (NM), ETA (hours), fuel (tonnes), safety score (%), and per-hazard risk breakdowns.
4. **Export Voyage PDF Report**:
   - Click **`📥 PDF Report`** on the navigation card to open and print/download an official NCPOR expedition voyage report.

---

## 📡 Core API Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/health` | `GET` | Health check & system mode status |
| `/api/data-status` | `GET` | Datasets load status (AMSR2, ERA5, GLORYS, etc.) |
| `/api/vessel-profiles` | `GET` | NCPOR research vessel profiles (R/V Bharathi) |
| `/api/sea-ice/current` | `GET` | Current AMSR2 sea ice concentration grid |
| `/api/sea-ice/forecast` | `GET` | Optical-flow sea ice nowcast (6h to 48h) |
| `/api/icebergs` | `GET` | List of detected BYU reference & SAR icebergs |
| `/api/icebergs/{id}/trajectory` | `GET` | LSTM predicted trajectory for specific iceberg |
| `/api/risk-map` | `GET` | Composite risk heatmap matrix |
| `/api/routes/optimize` | `POST` | Execute A* multi-objective route optimization |
| `/api/weather` | `GET` | ERA5 10m wind speed weather matrix |
| `/api/ocean` | `GET` | GLORYS ocean surface velocity vectors |
| `/api/overlays/{type}.png` | `GET` | Dynamic PNG overlay map tiles (sea-ice, risk, weather, bathymetry) |

---

## 📜 Project Directory Structure

```
antarctic-navigation/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route endpoints
│   │   ├── core/         # Grid transforms, settings, pipeline loader
│   │   ├── ml/           # LSTM, Optical Flow, CFAR model inference
│   │   ├── models/       # SQLAlchemy database schemas
│   │   └── services/     # Risk computation & A* route pathfinding
│   ├── DataSets/         # AMSR2, ERA5, GLORYS, GEBCO, Sentinel-1 files
│   ├── scripts/          # DB population & model training scripts
│   ├── pyproject.toml    # Python project dependencies (uv)
│   └── README.md         # Backend setup documentation
├── frontend/
│   ├── src/
│   │   ├── components/   # Leaflet Map component & controls
│   │   ├── data/         # Demo data fallbacks for offline mode
│   │   ├── hooks/        # Live API polling & demo hooks
│   │   ├── App.tsx       # Google Maps style full-screen UI
│   │   └── index.css     # Tailwind CSS styles & animations
│   ├── package.json      # Node.js dependencies
│   └── README.md         # Frontend setup documentation
├── INDIAN ANTARCTICA VESSELS NAVIGATION SYSTEM(IAVNS).md
└── README.md             # Project Root Overview
```

---

## 📄 License & Attribution
- Developed for **SIH PS-26059** under the guidance of **NCPOR**, **MoES**, and **ISRO**.
- Data sources: Copernicus Marine (CMEMS), NSIDC, ECMWF ERA5, GEBCO 2024, BYU MERS.
