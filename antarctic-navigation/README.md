# IAVNS: AI-Enabled Antarctic Navigation Decision Support System

This repository contains the backend and frontend for the POLARIS project, developed for the Smart India Hackathon (Problem Statement PS-26059).

The system integrates real NetCDF, TIFF, and CSV data from AMSR2 (Sea Ice), GEBCO (Bathymetry), ERA5 (Weather), GLORYS (Ocean Currents), Sentinel-1 (SAR), and BYU MERS (Iceberg Tracks) to generate dynamic risk maps and A* optimal routes.

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- The dataset folder must be located at `D:\IAVNS\DataSets` (as configured in `backend/app/core/config.py`).

---

## 1. Starting the Backend (FastAPI)

The backend handles all data loading, machine learning models (LSTM trajectory, Optical Flow nowcasting, CFAR SAR detection), and A* route optimization.

1. **Open a terminal** and navigate to the project root:
   ```bash
   cd d:\IAVNS\antarctic-navigation
   ```

2. **Activate the Python virtual environment**:
   ```bash
   venv\Scripts\activate
   ```
   *(If the virtual environment doesn't exist, create it: `python -m venv venv` and install requirements with `pip install -r backend/requirements.txt` or install `fastapi, uvicorn, xarray, netCDF4, rasterio, pandas, scikit-learn, scipy, opencv-python, sqlalchemy, pyproj`)*

3. **Initialize and populate the Database** (Run this once to seed the historical iceberg tracks and SAR candidates into SQLite):
   ```bash
   cd backend
   python scripts/populate_db.py
   ```
   *Note: This will take a moment as it processes 647 iceberg tracks and runs the CFAR detection on the Sentinel-1 scene.*

4. **Start the API server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   The backend is now running at [http://localhost:8000](http://localhost:8000). You can view the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 2. Starting the Frontend (React + Vite)

The frontend provides the interactive Leaflet map, dashboard, and layer controls.

1. **Open a new terminal** and navigate to the frontend directory:
   ```bash
   cd d:\IAVNS\antarctic-navigation\frontend
   ```

2. **Install Node dependencies** (Run this once):
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   The frontend will typically start at [http://localhost:5173](http://localhost:5173). 

4. Open your browser and navigate to the URL provided in the terminal to view the POLARIS dashboard.

---

## Architecture Notes

- **Data Pipeline (`pipeline.py`)**: Loads real data onto a unified `EPSG:3031` polar stereographic analysis grid upon first request. 
- **Dynamic Risk**: Risk maps are not hardcoded. They are calculated dynamically using real ICECON %, GEBCO bathymetry, ERA5 wind matrices, and true iceberg distances.
- **Machine Learning**: 
  - The LSTM trajectory model weights are pre-trained and saved in `backend/app/ml/artifacts/lstm_weights.npz`. 
  - To retrain the LSTM, you can run `python backend/scripts/train_lstm.py`.
- **Evaluation**: Please refer to `EVALUATION.md` for authentic accuracy and error metrics.
