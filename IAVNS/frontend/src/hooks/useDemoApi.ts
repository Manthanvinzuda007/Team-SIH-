import { useState, useEffect } from 'react';
import {
  DEMO_HEALTH, DEMO_ICEBERGS, DEMO_RISK_MAP, DEMO_SEA_ICE,
  DEMO_WEATHER, DEMO_BATHYMETRY, DEMO_OCEAN, DEMO_DATA_STATUS, DEMO_ML_STATUS,
  DEMO_ROUTES, DEMO_FORECAST, DEMO_TRAJECTORIES, ALL_DEMO_TRAJECTORIES, DEMO_TRAJECTORY_1,
  getDemoRoutes as calcDemoRoutes
} from '../data/demoData';

const DEMO_DATA_MAP: Record<string, any> = {
  '/health': DEMO_HEALTH,
  '/data-status': DEMO_DATA_STATUS,
  '/sea-ice/current': DEMO_SEA_ICE,
  '/sea-ice/forecast': DEMO_FORECAST,
  '/icebergs': DEMO_ICEBERGS,
  '/risk-map': DEMO_RISK_MAP,
  '/weather': DEMO_WEATHER,
  '/bathymetry': DEMO_BATHYMETRY,
  '/ocean': DEMO_OCEAN,
  '/ml/status': DEMO_ML_STATUS,
};

export function getDemoData(endpoint: string): any {
  if (endpoint.includes('/trajectories/all')) {
    return ALL_DEMO_TRAJECTORIES;
  }
  for (const key of Object.keys(DEMO_DATA_MAP)) {
    if (endpoint.startsWith(key) || endpoint.startsWith('/api' + key)) {
      return DEMO_DATA_MAP[key];
    }
  }
  if (endpoint.includes('/trajectory')) {
    const match = endpoint.match(/\/icebergs\/(\d+)\/trajectory/);
    if (match && match[1] && DEMO_TRAJECTORIES[match[1]]) {
      return DEMO_TRAJECTORIES[match[1]];
    }
    return DEMO_TRAJECTORY_1;
  }
  if (endpoint.includes('/routes/optimize')) return DEMO_ROUTES;
  return null;
}

export function getDemoRoutes(origin?: { lat: number; lon: number }, dest?: { lat: number; lon: number }) {
  return calcDemoRoutes(origin, dest);
}

/**
 * useDemoPollingApi — always-safe hook (no conditional call needed).
 * Returns demo data after a small simulated delay.
 */
export function useDemoPollingApi<T = any>(endpoint: string, _intervalMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error] = useState<Error | null>(null);

  useEffect(() => {
    setIsLoading(true);
    const key = endpoint.split('?')[0].replace('/api', '');
    const demoValue = getDemoData(key);
    const delay = Math.random() * 300 + 100;
    const timer = setTimeout(() => {
      if (demoValue) setData(demoValue as T);
      setIsLoading(false);
    }, delay);
    return () => clearTimeout(timer);
  }, [endpoint]);

  return { data, isLoading, error };
}
