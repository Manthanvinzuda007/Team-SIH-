// IAVNS Demo Data — realistic mock data for judge demonstrations
// Used when backend is offline. All coordinates are in the Southern Ocean.
// Data is based on the real dataset window: Aug 2026, Antarctic Peninsula region.

export const DEMO_HEALTH = {
  status: 'ok',
  system: 'IAVNS — Indian Antarctica Vessels Navigation System',
  version: '1.0.0',
  advisory_only: true,
  mode: 'HISTORICAL_DEMO',
  dataset_configured: true,
  disclaimer: 'DEMO MODE — Static data for demonstration. Not a live operational feed.',
  timestamp: new Date().toISOString(),
};

export const DEMO_ICEBERGS = {
  count: 18,
  limit: 200,
  icebergs: [
    // BYU Reference icebergs (confirmed large tabular)
    { id: 1, name: 'A-68A', lat: -63.2, lon: -57.8, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.98, status: 'HISTORICAL', size_length_nm: 45.2, size_width_nm: 18.6, speed_knots: 0.3, heading_deg: 275 },
    { id: 2, name: 'A-76A', lat: -64.1, lon: -55.3, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.95, status: 'HISTORICAL', size_length_nm: 32.1, size_width_nm: 14.2, speed_knots: 0.2, heading_deg: 290 },
    { id: 3, name: 'B-22A', lat: -65.8, lon: -62.4, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.92, status: 'HISTORICAL', size_length_nm: 28.4, size_width_nm: 12.1, speed_knots: 0.4, heading_deg: 260 },
    { id: 4, name: 'C-19A', lat: -67.3, lon: -48.2, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.88, status: 'HISTORICAL', size_length_nm: 21.7, size_width_nm: 9.8, speed_knots: 0.5, heading_deg: 285 },
    { id: 5, name: 'D-15A', lat: -62.7, lon: -44.5, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.91, status: 'HISTORICAL', size_length_nm: 18.3, size_width_nm: 7.6, speed_knots: 0.6, heading_deg: 270 },
    { id: 6, name: 'B-34', lat: -70.1, lon: -58.6, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.86, status: 'HISTORICAL', size_length_nm: 15.9, size_width_nm: 6.4, speed_knots: 0.3, heading_deg: 280 },
    { id: 7, name: 'C-37A', lat: -68.4, lon: -38.7, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.83, status: 'HISTORICAL', size_length_nm: 12.2, size_width_nm: 5.1, speed_knots: 0.7, heading_deg: 265 },
    { id: 8, name: 'A-23A', lat: -71.2, lon: -28.4, source: 'BYU_MERS', category: 'REFERENCE_CONFIRMED', confidence: 0.97, status: 'HISTORICAL', size_length_nm: 38.6, size_width_nm: 16.3, speed_knots: 0.1, heading_deg: 315 },
    // SAR CFAR candidates (Sentinel-1 detections)
    { id: 9, name: 'SAR-001', lat: -64.5, lon: -59.2, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.74, status: 'CANDIDATE', size_length_nm: 2.1, size_width_nm: 0.9, speed_knots: null, heading_deg: null },
    { id: 10, name: 'SAR-002', lat: -65.1, lon: -56.8, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.68, status: 'CANDIDATE', size_length_nm: 1.8, size_width_nm: 0.7, speed_knots: null, heading_deg: null },
    { id: 11, name: 'SAR-003', lat: -66.7, lon: -61.3, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.71, status: 'CANDIDATE', size_length_nm: 3.2, size_width_nm: 1.4, speed_knots: null, heading_deg: null },
    { id: 12, name: 'SAR-004', lat: -63.8, lon: -52.6, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.65, status: 'CANDIDATE', size_length_nm: 1.5, size_width_nm: 0.6, speed_knots: null, heading_deg: null },
    { id: 13, name: 'SAR-005', lat: -67.2, lon: -47.1, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.78, status: 'CANDIDATE', size_length_nm: 4.8, size_width_nm: 2.1, speed_knots: null, heading_deg: null },
    { id: 14, name: 'SAR-006', lat: -62.4, lon: -42.8, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.62, status: 'CANDIDATE', size_length_nm: 1.2, size_width_nm: 0.5, speed_knots: null, heading_deg: null },
    { id: 15, name: 'SAR-007', lat: -69.5, lon: -35.4, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.70, status: 'CANDIDATE', size_length_nm: 2.7, size_width_nm: 1.1, speed_knots: null, heading_deg: null },
    { id: 16, name: 'SAR-008', lat: -64.9, lon: -31.2, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.66, status: 'CANDIDATE', size_length_nm: 1.9, size_width_nm: 0.8, speed_knots: null, heading_deg: null },
    { id: 17, name: 'SAR-009', lat: -63.3, lon: -66.5, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.73, status: 'CANDIDATE', size_length_nm: 3.5, size_width_nm: 1.5, speed_knots: null, heading_deg: null },
    { id: 18, name: 'SAR-010', lat: -61.8, lon: -71.2, source: 'S1_CFAR', category: 'SAR_CANDIDATE', confidence: 0.59, status: 'CANDIDATE', size_length_nm: 2.3, size_width_nm: 1.0, speed_knots: null, heading_deg: null },
  ]
};

export const DEMO_RISK_MAP = {
  status: 'ok',
  cells_computed: 847,
  mean_risk: 34.2,
  max_risk: 87.6,
  high_risk_cells: 124,
  medium_risk_cells: 289,
  low_risk_cells: 434,
  provenance: {
    weights: { ice: 0.30, iceberg: 0.25, weather: 0.20, bathymetry: 0.15, current: 0.10 }
  },
  overlay: { url: null, bounds: [[-85.0, -180.0], [85.0, 180.0]] },
  risk_cells: [] as any[], // populated below
};

export const DEMO_SEA_ICE = {
  status: 'HISTORICAL',
  valid_time: '2026-08-08',
  source: 'NSIDC-0803 AMSR2 ICECON',
  units: 'percent (0–100)',
  native_grid: 'EPSG:3412 25 km, 8 days 2026-08-01..08',
  temporal_status: 'HISTORICAL — static file, not a live satellite feed',
  grid: [] as any[],
  overlay: { url: null, bounds: [[-85.0, -180.0], [85.0, 180.0]] },
  forecast_backtest: {
    persistence_mae_fraction: 0.0421,
    advection_mae_fraction: 0.0318,
    persistence_mae_pairs: 7,
    advection_mae_pairs: 7
  },
  limitation: 'Eight daily fields only — 2026-08-01..08. Optical-flow advection is the production model.'
};

export const DEMO_WEATHER = {
  source: 'ERA5 instant+accum merged (u10, v10, t2m, msl, tp)',
  valid_time: '2026-08-08T23:00:00Z',
  temporal_status: 'HISTORICAL — static ERA5 reanalysis',
  stats: {
    wind_speed_ms: { mean: 8.4, max: 22.1, min: 0.3, std: 4.2 },
    t2m_K: { mean: 262.3, max: 271.1, min: 251.8, std: 4.7 },
    msl_Pa: { mean: 98642, max: 101320, min: 95421, std: 1240 },
  },
  note: 'No wave-height file in dataset; wind speed is weather-risk proxy.',
  overlay: { url: null, bounds: [[-85.0, -180.0], [85.0, 180.0]] },
};

export const DEMO_OCEAN = {
  source: 'CMEMS GLORYS12 daily-mean reanalysis',
  valid_time: '2026-06-01..08 mean',
  temporal_status: 'HISTORICAL',
  depth: 'surface (~0.494 m)',
  n_vectors: 156,
  temporal_warning: 'GLORYS data are June 2026; AMSR2/ERA5 are August 2026. Currents cannot be assumed to match ice conditions.',
  vectors: [
    // Generate some representative ocean current vectors in the Antarctic Peninsula region
    { lat: -63.0, lon: -60.0, u_ms: -0.24, v_ms: 0.08, speed_ms: 0.25, speed_knots: 0.49 },
    { lat: -64.0, lon: -58.0, u_ms: -0.31, v_ms: 0.12, speed_ms: 0.33, speed_knots: 0.64 },
    { lat: -65.0, lon: -56.0, u_ms: -0.18, v_ms: 0.05, speed_ms: 0.19, speed_knots: 0.37 },
    { lat: -66.0, lon: -54.0, u_ms: -0.42, v_ms: 0.15, speed_ms: 0.44, speed_knots: 0.86 },
    { lat: -67.0, lon: -52.0, u_ms: -0.28, v_ms: 0.09, speed_ms: 0.30, speed_knots: 0.58 },
    { lat: -68.0, lon: -50.0, u_ms: -0.35, v_ms: 0.11, speed_ms: 0.37, speed_knots: 0.71 },
    { lat: -63.0, lon: -50.0, u_ms: -0.19, v_ms: 0.06, speed_ms: 0.20, speed_knots: 0.39 },
    { lat: -65.0, lon: -45.0, u_ms: -0.48, v_ms: 0.16, speed_ms: 0.51, speed_knots: 0.99 },
    { lat: -67.0, lon: -42.0, u_ms: -0.22, v_ms: 0.07, speed_ms: 0.23, speed_knots: 0.45 },
    { lat: -64.0, lon: -38.0, u_ms: -0.39, v_ms: 0.13, speed_ms: 0.41, speed_knots: 0.80 },
    { lat: -66.0, lon: -35.0, u_ms: -0.25, v_ms: 0.08, speed_ms: 0.26, speed_knots: 0.51 },
    { lat: -70.0, lon: -55.0, u_ms: -0.14, v_ms: 0.04, speed_ms: 0.15, speed_knots: 0.29 },
  ]
};

export const DEMO_DATA_STATUS = {
  dataset_root: 'D:\\Hackathon\\SIH 26\\antarctic-navigation\\backend\\DataSets',
  demo_window: 'Sea ice + ERA5: 2026-08-01..08. GLORYS: 2026-06-01..08 mean. SAR: 2026-08-22. BYU: multi-decade.',
  datasets: [
    { name: 'seaice', status: 'LOADED', files_found: 8, bytes_on_disk: 52428800, data_age_hours: 312.4, time_range: '2026-08-01 to 2026-08-08' },
    { name: 'gebco', status: 'LOADED', files_found: 1, bytes_on_disk: 986542080, data_age_hours: 8760.0, time_range: 'STATIC' },
    { name: 'era5', status: 'LOADED', files_found: 2, bytes_on_disk: 201326592, data_age_hours: 312.4, time_range: '2026-08-01 to 2026-08-08' },
    { name: 'glorys', status: 'LOADED', files_found: 1, bytes_on_disk: 134217728, data_age_hours: 2208.0, time_range: '2026-06-01 to 2026-06-08' },
    { name: 'sentinel1', status: 'LOADED', files_found: 1, bytes_on_disk: 524288000, data_age_hours: 288.0, time_range: '2026-08-22' },
    { name: 'iceberg', status: 'LOADED', files_found: 1, bytes_on_disk: 8388608, data_age_hours: 87600.0, time_range: 'MULTI-DECADE BYU' },
  ]
};

export const DEMO_ML_STATUS = {
  iceberg_trajectory: {
    model_name: 'IcebergTrajectoryPredictor',
    model_status: 'LSTM',
    forecast_horizons_h: [24, 72, 168],
    n_tracks_used: 531,
    n_tracks_total: 625,
    metrics: {
      ADE_km: {
        '1d': { baseline_persistence_velocity: 18.4, lstm: 14.2 },
        '3d': { baseline_persistence_velocity: 42.7, lstm: 31.8 },
        '7d': { baseline_persistence_velocity: 89.3, lstm: 61.4 },
      }
    }
  },
  sar_iceberg_detection: {
    model_name: 'CFARDetector + YOLOv8',
    model_status: 'CFAR+ML',
    precision: 0.81,
    recall: 0.68,
    f1: 0.74,
    note: 'CFAR pre-screening followed by CNN classification on Sentinel-1 IW GRD.'
  },
  sea_ice_nowcast: {
    model_name: 'SeaIceForecaster (Optical Flow)',
    model_status: 'OPTICAL_FLOW',
    available: true,
    horizon_h: 48,
    confidence: 0.847,
    metrics: { persistence_mae_fraction: 0.0421, advection_mae_fraction: 0.0318 }
  },
  timestamp: new Date().toISOString(),
};

function generateCurvedPath(waypoints: Array<{ lat: number; lon: number }>, stepsPerSegment: number = 8) {
  const points: Array<{ lat: number; lon: number }> = [];
  for (let i = 0; i < waypoints.length - 1; i++) {
    const p1 = waypoints[i];
    const p2 = waypoints[i + 1];
    for (let step = 0; step < stepsPerSegment; step++) {
      const t = step / stepsPerSegment;
      // Smooth cosine interpolation
      const ft = (1 - Math.cos(t * Math.PI)) * 0.5;
      points.push({
        lat: Number((p1.lat * (1 - ft) + p2.lat * ft).toFixed(4)),
        lon: Number((p1.lon * (1 - ft) + p2.lon * ft).toFixed(4)),
      });
    }
  }
  points.push(waypoints[waypoints.length - 1]);
  return points;
}

export const DEMO_ROUTES = {
  routes: [
    {
      id: 1,
      mode: 'FASTEST',
      path_points: generateCurvedPath([
        { lat: -63.5, lon: -60.0 },
        { lat: -64.1, lon: -57.5 },
        { lat: -64.8, lon: -54.8 },
        { lat: -65.6, lon: -52.2 },
        { lat: -66.4, lon: -49.0 },
        { lat: -67.2, lon: -45.5 },
        { lat: -67.8, lon: -42.2 },
        { lat: -68.0, lon: -40.0 },
      ]),
      distance_nm: 684.2,
      estimated_time_hours: 57.0,
      base_speed_knots: 12.0,
      fuel_tonnes: 88.9,
      fuel_model: 'distance_proxy_0.13t_per_nm',
      safety_score: 62.4,
      risk_score: 37.6,
      ice_encounters: 23,
      route_score: 71.2,
      fallback: false,
      explanation_text: 'Direct route. Crosses moderate sea-ice (15–40% conc.) in mid-section. 23 cells exceed 15% threshold. Higher fuel efficiency.',
      data_valid_time: '2026-08-08 (AMSR2 last frame)',
      warnings: ['Crosses ice-dense region near 65.5°S 51°W — consider ice class rating'],
      risk_breakdown: {
        total: 37.6,
        sea_ice: 48.2,
        iceberg_total: 31.4,
        weather: 28.7,
        bathymetry: 8.3,
        current: 21.4
      },
      data_availability: { sea_ice: true, iceberg_proximity: true, weather: true, bathymetry: true, ocean_currents: true },
      weights: { distance: 1.5, safety: 0.3, fuel: 0.4, current: 0.2 },
      computed_at: new Date().toISOString(),
    },
    {
      id: 2,
      mode: 'SAFEST',
      path_points: generateCurvedPath([
        { lat: -63.5, lon: -60.0 },
        { lat: -62.6, lon: -57.8 },
        { lat: -61.9, lon: -53.5 },
        { lat: -61.5, lon: -48.2 },
        { lat: -62.1, lon: -44.0 },
        { lat: -63.5, lon: -41.2 },
        { lat: -65.4, lon: -40.5 },
        { lat: -67.2, lon: -40.1 },
        { lat: -68.0, lon: -40.0 },
      ]),
      distance_nm: 821.7,
      estimated_time_hours: 68.5,
      base_speed_knots: 12.0,
      fuel_tonnes: 106.8,
      fuel_model: 'distance_proxy_0.13t_per_nm',
      safety_score: 91.2,
      risk_score: 8.8,
      ice_encounters: 2,
      route_score: 88.6,
      fallback: false,
      explanation_text: 'Northern detour through open water. Avoids dense ice pack and 6 major iceberg positions. Only 2 minor ice encounters. +20% distance vs FASTEST.',
      data_valid_time: '2026-08-08 (AMSR2 last frame)',
      warnings: [],
      risk_breakdown: {
        total: 8.8,
        sea_ice: 6.4,
        iceberg_total: 8.1,
        weather: 12.3,
        bathymetry: 4.2,
        current: 13.1
      },
      data_availability: { sea_ice: true, iceberg_proximity: true, weather: true, bathymetry: true, ocean_currents: true },
      weights: { distance: 0.5, safety: 1.5, fuel: 0.2, current: 0.3 },
      computed_at: new Date().toISOString(),
    },
    {
      id: 3,
      mode: 'BALANCED',
      path_points: generateCurvedPath([
        { lat: -63.5, lon: -60.0 },
        { lat: -63.1, lon: -57.2 },
        { lat: -63.4, lon: -53.8 },
        { lat: -64.2, lon: -50.1 },
        { lat: -65.3, lon: -46.5 },
        { lat: -66.4, lon: -43.2 },
        { lat: -67.5, lon: -41.0 },
        { lat: -68.0, lon: -40.0 },
      ]),
      distance_nm: 731.4,
      estimated_time_hours: 61.0,
      base_speed_knots: 12.0,
      fuel_tonnes: 95.1,
      fuel_model: 'distance_proxy_0.13t_per_nm',
      safety_score: 78.9,
      risk_score: 21.1,
      ice_encounters: 8,
      route_score: 82.3,
      fallback: false,
      explanation_text: 'Balanced route. Slight northern detour avoids densest ice zones while maintaining acceptable distance. Iceberg encounter probability reduced by 65% vs FASTEST. Recommended for R/V Bharathi (PC5 class).',
      data_valid_time: '2026-08-08 (AMSR2 last frame)',
      warnings: ['Minor ice encountered near 65°S 48°W (15–25% conc.)'],
      risk_breakdown: {
        total: 21.1,
        sea_ice: 18.7,
        iceberg_total: 19.3,
        weather: 22.4,
        bathymetry: 6.1,
        current: 17.2
      },
      data_availability: { sea_ice: true, iceberg_proximity: true, weather: true, bathymetry: true, ocean_currents: true },
      weights: { distance: 1.0, safety: 0.8, fuel: 0.5, current: 0.3 },
      computed_at: new Date().toISOString(),
    }
  ],
  vessel_config: {
    ice_class: 'PC5',
    draft_m: 6.15,
    max_speed_knots: 15.0,
    icebreaking_capable: true,
    dedicated_icebreaker: false
  },
  computed_at: new Date().toISOString(),
};

export const DEMO_FORECAST = {
  requested_hours: [6, 12, 18, 24, 30, 36, 42, 48],
  supported_horizons: [6, 12, 18, 24, 30, 36, 42, 48],
  note: 'Nowcast on native AMSR2 grid. Honest horizon ~24–48h with 8-day corpus.',
  temporal_status: 'HISTORICAL — static 2026-08-08 field as initial condition',
  backtest: { persistence_mae_fraction: 0.0421, advection_mae_fraction: 0.0318, persistence_mae_pairs: 7, advection_mae_pairs: 7 },
  forecasts: [
    { forecast_hour: 6,  model_type: 'OPTICAL_FLOW', confidence: 0.94, mean_concentration_fraction: 0.412, status: 'AVAILABLE', horizon_note: 'High confidence short-range' },
    { forecast_hour: 12, model_type: 'OPTICAL_FLOW', confidence: 0.89, mean_concentration_fraction: 0.418, status: 'AVAILABLE', horizon_note: 'High confidence' },
    { forecast_hour: 18, model_type: 'OPTICAL_FLOW', confidence: 0.85, mean_concentration_fraction: 0.423, status: 'AVAILABLE', horizon_note: 'Medium-high confidence' },
    { forecast_hour: 24, model_type: 'OPTICAL_FLOW', confidence: 0.81, mean_concentration_fraction: 0.429, status: 'AVAILABLE', horizon_note: 'Medium confidence' },
    { forecast_hour: 30, model_type: 'OPTICAL_FLOW', confidence: 0.74, mean_concentration_fraction: 0.436, status: 'AVAILABLE', horizon_note: 'Medium confidence' },
    { forecast_hour: 36, model_type: 'OPTICAL_FLOW', confidence: 0.67, mean_concentration_fraction: 0.441, status: 'AVAILABLE', horizon_note: 'Lower confidence' },
    { forecast_hour: 42, model_type: 'OPTICAL_FLOW', confidence: 0.61, mean_concentration_fraction: 0.447, status: 'AVAILABLE', horizon_note: 'Lower confidence' },
    { forecast_hour: 48, model_type: 'OPTICAL_FLOW', confidence: 0.54, mean_concentration_fraction: 0.453, status: 'AVAILABLE', horizon_note: 'Marginal confidence' },
  ]
};

// Predicted trajectory for iceberg A-68A (demo)
export const DEMO_TRAJECTORY_1 = {
  iceberg_id: 1,
  historical_points: [
    { lat: -63.8, lon: -56.2, timestamp: '2026-08-01T00:00:00Z' },
    { lat: -63.6, lon: -57.0, timestamp: '2026-08-02T00:00:00Z' },
    { lat: -63.4, lon: -57.5, timestamp: '2026-08-03T00:00:00Z' },
    { lat: -63.3, lon: -57.8, timestamp: '2026-08-04T00:00:00Z' },
    { lat: -63.2, lon: -57.8, timestamp: '2026-08-08T00:00:00Z' },
  ],
  predicted_points: [
    { forecast_hour: 24, lat: -63.1, lon: -58.2 },
    { forecast_hour: 72, lat: -62.9, lon: -59.1 },
    { forecast_hour: 168, lat: -62.6, lon: -60.4 },
  ],
  confidence_corridor_km: 31.8,
  model_type: 'LSTM',
  model_status: 'LSTM',
};
