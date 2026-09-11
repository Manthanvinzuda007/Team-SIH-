// IAVNS Extracted Backend Data & Standalone Demo Provider
// Pre-computed from real backend dataset pipeline (AMSR2, GEBCO, ERA5, GLORYS, Sentinel-1, BYU MERS)
// Allows frontend to run standalone on Vercel without backend dependency.

import extractedData from './extractedBackendData.json';

export const DEMO_HEALTH = extractedData.health;
export const DEMO_ICEBERGS = extractedData.icebergs;
export const DEMO_RISK_MAP = extractedData.risk_map;
export const DEMO_SEA_ICE = extractedData.sea_ice;
export const DEMO_FORECAST = extractedData.sea_ice_forecast;
export const DEMO_WEATHER = extractedData.weather;
export const DEMO_BATHYMETRY = extractedData.bathymetry;
export const DEMO_OCEAN = extractedData.ocean;
export const DEMO_DATA_STATUS = extractedData.data_status;
export const DEMO_ML_STATUS = extractedData.ml_status;
export const DEMO_ROUTES = extractedData.routes;
export const DEMO_TRAJECTORIES = extractedData.trajectories as Record<string, any>;
export const ALL_DEMO_TRAJECTORIES = Object.values(DEMO_TRAJECTORIES);
export const DEMO_TRAJECTORY_1 = DEMO_TRAJECTORIES["1"] || DEMO_TRAJECTORIES[Object.keys(DEMO_TRAJECTORIES)[0]];

function generateCurvedPath(waypoints: Array<{ lat: number; lon: number }>, stepsPerSegment: number = 8) {
  const points: Array<{ lat: number; lon: number }> = [];
  for (let i = 0; i < waypoints.length - 1; i++) {
    const p1 = waypoints[i];
    const p2 = waypoints[i + 1];
    for (let step = 0; step < stepsPerSegment; step++) {
      const t = step / stepsPerSegment;
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

export function getDemoRoutes(origin?: { lat: number; lon: number }, dest?: { lat: number; lon: number }) {
  if (!origin || !dest || (origin.lat === -63.5 && origin.lon === -60.0 && dest.lat === -68.0 && dest.lon === -40.0)) {
    return DEMO_ROUTES;
  }

  const dLat = dest.lat - origin.lat;
  const dLon = dest.lon - origin.lon;
  const avgLatRad = ((origin.lat + dest.lat) / 2) * (Math.PI / 180);
  const distNM = Math.round(Math.sqrt(Math.pow(dLat * 60, 2) + Math.pow(dLon * 60 * Math.cos(avgLatRad), 2)) * 10) / 10;

  const modes = ['FASTEST', 'SAFEST', 'BALANCED', 'CUSTOM'];
  const routes = modes.map((m) => {
    const curveOffset = m === 'SAFEST' ? 1.2 : m === 'FASTEST' ? 0.2 : 0.6;
    const waypoints = [
      origin,
      { lat: Number((origin.lat + dLat * 0.25 - curveOffset * 0.3).toFixed(4)), lon: Number((origin.lon + dLon * 0.25 + curveOffset * 0.5).toFixed(4)) },
      { lat: Number((origin.lat + dLat * 0.5 - curveOffset * 0.5).toFixed(4)), lon: Number((origin.lon + dLon * 0.5 + curveOffset * 0.8).toFixed(4)) },
      { lat: Number((origin.lat + dLat * 0.75 - curveOffset * 0.3).toFixed(4)), lon: Number((origin.lon + dLon * 0.75 + curveOffset * 0.4).toFixed(4)) },
      dest
    ];
    const path_points = generateCurvedPath(waypoints, 6);
    const speed = m === 'FASTEST' ? 14.0 : m === 'SAFEST' ? 10.5 : 12.0;
    const eta = Math.round((distNM / speed) * 10) / 10;
    const fuel = Math.round((distNM * 0.13) * 10) / 10;
    const safety = m === 'SAFEST' ? 94.2 : m === 'FASTEST' ? 62.4 : 85.0;
    const risk = Math.round((100 - safety) * 10) / 10;

    return {
      id: m === 'FASTEST' ? 1 : m === 'SAFEST' ? 2 : m === 'BALANCED' ? 3 : 4,
      mode: m,
      path_points,
      distance_nm: distNM,
      estimated_time_hours: eta,
      base_speed_knots: speed,
      fuel_tonnes: fuel,
      fuel_model: 'distance_proxy_0.13t_per_nm',
      safety_score: safety,
      risk_score: risk,
      risk_breakdown: {
        sea_ice: m === 'SAFEST' ? 12.1 : 35.4,
        iceberg_total: m === 'SAFEST' ? 8.4 : 22.1,
        weather: 15.2,
        bathymetry: 5.1,
        current: 3.2
      },
      explanation_text: `Optimal ${m.toLowerCase()} transit path between ${origin.lat}°S, ${origin.lon}°W and ${dest.lat}°S, ${dest.lon}°W avoiding heavy pack ice and detected icebergs.`
    };
  });

  return { routes };
}
