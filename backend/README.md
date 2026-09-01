# ⚙️ IAVNS Backend API (FastAPI)

FastAPI-powered Python backend for the **Indian Antarctica Vessels Navigation System (IAVNS)**.

The backend handles:
- Environmental dataset ingestion (AMSR2 sea ice, ERA5 weather, GLORYS ocean currents, GEBCO bathymetry).
- Machine learning models:
  - **LSTM Trajectory Predictor**: 24h, 72h, and 168h iceberg path forecasting.
  - **Optical Flow Sea-Ice Nowcaster**: 6h to 48h sea-ice advection forecasts.
  - **CFAR Detector**: Sentinel-1 SAR candidate target detection.
- **A* Safe Pathfinding Algorithm**: Multi-objective path optimization with cell snapping (`_find_nearest_unblocked_cell`) and vessel ice class constraints.
- Dynamic PNG heatmap overlay generator (`EPSG:3031` polar stereographic to Web Mercator).

---

## 🚀 Setup & Execution

### 1. Prerequisites
- **Python 3.11** or **Python 3.12**
- **uv** (Recommended) or standard `pip` / `venv`

### 2. Environment Configuration
Create or edit `backend/.env`:
```ini
APP_NAME="IAVNS Antarctic Navigation"
APP_FULL_NAME="Indian Antarctica Vessels Navigation System"
IAVNS_DATA_DIR=./DataSets
DATABASE_URL=sqlite:///./iavns.db
CORS_ORIGINS=["http://localhost:5173","http://localhost:5174"]
MAX_ICE_CONCENTRATION=80.0
MIN_DEPTH_MARGIN_M=10.0
```

### 3. Installation & Setup

1. **Install Dependencies**:
   ```bash
   uv sync
   ```
   *(This automatically creates `.venv` and installs all dependencies in seconds.)*

2. **Activate the Virtual Environment**:
   ```bash
   # Windows (PowerShell)
   .\.venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate
   ```

3. **Populate Historical Database (Run Once)**:
   ```bash
   python scripts/populate_db.py
   ```

4. **Launch API Server**:
   ```bash
   uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
   ```

---

## 📡 Key API Endpoints

- **`GET /api/health`**: Health status check & dataset configuration check.
- **`GET /api/vessel-profiles`**: Profiles for R/V Bharathi and other polar vessels.
- **`GET /api/sea-ice/current`**: Current AMSR2 sea ice concentration grid.
- **`GET /api/sea-ice/forecast`**: Optical flow nowcast for 6h to 48h horizons.
- **`GET /api/icebergs`**: Detected iceberg records (BYU reference & SAR candidates).
- **`GET /api/icebergs/{id}/trajectory`**: LSTM predicted trajectory for a specific iceberg.
- **`GET /api/risk-map`**: Dynamic composite risk score grid.
- **`POST /api/routes/optimize`**: Run A* pathfinder for FASTEST, SAFEST, BALANCED, or CUSTOM route modes.
- **`GET /api/weather`**: ERA5 10m wind speed matrix.
- **`GET /api/ocean`**: GLORYS surface current velocity vectors.
- **`GET /api/overlays/{sea-ice,risk,weather,bathymetry}.png`**: Dynamic PNG overlays.
- **Interactive Documentation**: Available at **`http://localhost:8000/docs`**.
