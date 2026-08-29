// ============================================================================
// Weather Service - Backend API Integration
// ============================================================================

import { apiRequest } from './api'
import type {
  WeatherGridResponse,
  WeatherPoint,
  MapBounds
} from '../types/api.types'

// ────────────────────────────────────────────────────────────────────────────
// API ENDPOINTS
// ────────────────────────────────────────────────────────────────────────────

/**
 * Fetch weather data for a given map bounds and time
 *
 * Backend API should implement:
 * GET /weather/grid?minLon=-180&maxLon=180&minLat=-90&maxLat=-60&time=2026-08-29T08:00:00Z
 *
 * Returns: WeatherGridResponse
 */
export async function fetchWeatherGrid(
  bounds: MapBounds,
  time?: string
): Promise<WeatherGridResponse> {
  const params = new URLSearchParams({
    minLon: bounds.minLon.toString(),
    maxLon: bounds.maxLon.toString(),
    minLat: bounds.minLat.toString(),
    maxLat: bounds.maxLat.toString(),
  })

  if (time) {
    params.append('time', time)
  }

  return apiRequest<WeatherGridResponse>(`/weather/grid?${params}`)
}

/**
 * Fetch weather at specific point
 *
 * Backend API:
 * GET /weather/point?lon=45&lat=-70&time=2026-08-29T08:00:00Z
 */
export async function fetchWeatherPoint(
  lon: number,
  lat: number,
  time?: string
): Promise<WeatherPoint> {
  const params = new URLSearchParams({
    lon: lon.toString(),
    lat: lat.toString(),
  })

  if (time) {
    params.append('time', time)
  }

  return apiRequest<WeatherPoint>(`/weather/point?${params}`)
}

// ────────────────────────────────────────────────────────────────────────────
// MOCK DATA (Remove when backend is ready)
// ────────────────────────────────────────────────────────────────────────────

export function getMockWeatherGrid(bounds: MapBounds): WeatherGridResponse {
  const gridPoints: WeatherPoint[] = []

  // Generate grid every 5 degrees
  for (let lon = Math.floor(bounds.minLon / 5) * 5; lon <= bounds.maxLon; lon += 5) {
    for (let lat = Math.floor(bounds.minLat / 5) * 5; lat <= bounds.maxLat; lat += 5) {
      // Simulate Antarctic weather patterns
      const distFromPole = Math.abs(lat + 90)
      const baseWindSpeed = 15 + distFromPole * 0.5 + Math.random() * 10
      const windDirection = (lon * 2 + 180) % 360 // Circumpolar westerlies

      gridPoints.push({
        longitude: lon,
        latitude: lat,
        wind: {
          speed: Math.round(baseWindSpeed),
          direction: Math.round(windDirection),
          gust: Math.round(baseWindSpeed * 1.3),
        },
        waves: {
          height: Math.round((baseWindSpeed / 10) * 10) / 10,
          period: Math.round(5 + baseWindSpeed / 5),
          direction: windDirection,
        },
        visibility: Math.max(1, 10 - baseWindSpeed / 5),
        temperature: -2 - distFromPole * 0.3,
        pressure: 980 + Math.random() * 40,
        timestamp: new Date().toISOString(),
      })
    }
  }

  return {
    gridPoints,
    timestamp: new Date().toISOString(),
    source: 'ECMWF (Mock)',
    validUntil: new Date(Date.now() + 6 * 3600000).toISOString(), // +6 hours
  }
}

// ────────────────────────────────────────────────────────────────────────────
// USE MOCK OR REAL API
// ────────────────────────────────────────────────────────────────────────────

const USE_MOCK_DATA = true // Set to false when backend is ready

export async function getWeatherGrid(bounds: MapBounds, time?: string): Promise<WeatherGridResponse> {
  if (USE_MOCK_DATA) {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 300))
    return getMockWeatherGrid(bounds)
  }

  return fetchWeatherGrid(bounds, time)
}
