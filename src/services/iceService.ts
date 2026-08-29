// ============================================================================
// Ice Thickness Service - Backend API Integration
// ============================================================================

import { apiRequest } from './api'
import type {
  IceThicknessGridResponse,
  IceThicknessPoint,
  MapBounds
} from '../types/api.types'

// ────────────────────────────────────────────────────────────────────────────
// API ENDPOINTS
// ────────────────────────────────────────────────────────────────────────────

/**
 * Fetch ice thickness data for a given map bounds
 *
 * Backend API should implement:
 * GET /ice/thickness?minLon=30&maxLon=60&minLat=-75&maxLat=-65&time=2026-08-29T08:00:00Z
 *
 * Returns: IceThicknessGridResponse
 */
export async function fetchIceThicknessGrid(
  bounds: MapBounds,
  time?: string
): Promise<IceThicknessGridResponse> {
  const params = new URLSearchParams({
    minLon: bounds.minLon.toString(),
    maxLon: bounds.maxLon.toString(),
    minLat: bounds.minLat.toString(),
    maxLat: bounds.maxLat.toString(),
  })

  if (time) {
    params.append('time', time)
  }

  return apiRequest<IceThicknessGridResponse>(`/ice/thickness?${params}`)
}

// ────────────────────────────────────────────────────────────────────────────
// MOCK DATA (Remove when backend is ready)
// ────────────────────────────────────────────────────────────────────────────

export function getMockIceThicknessGrid(bounds: MapBounds): IceThicknessGridResponse {
  const gridPoints: IceThicknessPoint[] = []

  // Generate ice thickness grid every 0.5 degrees
  for (let lon = bounds.minLon; lon <= bounds.maxLon; lon += 0.5) {
    for (let lat = bounds.minLat; lat <= bounds.maxLat; lat += 0.5) {
      const distFromCoast = Math.abs(lat + 68) // Approximate ice edge at -68°

      // Ice gets thicker further south
      let thickness = 0
      let concentration = 0
      let type: 'first-year' | 'multi-year' | 'fast-ice' | 'pack-ice' = 'pack-ice'

      if (distFromCoast > 2) {
        // Ice zone
        thickness = Math.max(0, (distFromCoast - 2) * 0.3 + Math.random() * 0.5)
        concentration = Math.min(100, distFromCoast * 15 + Math.random() * 20)

        if (thickness > 2) {
          type = 'multi-year'
        } else if (thickness > 1) {
          type = 'first-year'
        } else if (concentration > 80) {
          type = 'pack-ice'
        } else {
          type = 'pack-ice'
        }
      }

      if (concentration > 5 || thickness > 0.1) {
        gridPoints.push({
          longitude: lon,
          latitude: lat,
          thickness: Math.round(thickness * 100) / 100,
          concentration: Math.round(concentration),
          type,
          confidence: 85 + Math.random() * 15,
        })
      }
    }
  }

  return {
    gridPoints,
    resolution: 6.25, // km (AMSR2 resolution)
    timestamp: new Date().toISOString(),
    source: 'AMSR2 (Mock)',
    validUntil: new Date(Date.now() + 24 * 3600000).toISOString(), // +24 hours
  }
}

// ────────────────────────────────────────────────────────────────────────────
// SAFE SPEED CALCULATION
// ────────────────────────────────────────────────────────────────────────────

/**
 * Calculate safe vessel speed based on ice class and ice thickness
 * According to IMO Polar Code guidelines
 */
export function calculateSafeSpeed(
  iceClass: string,
  thickness: number,
  concentration: number
): { maxSpeed: number; recommended: number; warning?: string } {
  // Polar Class ice capabilities (simplified)
  const iceClassLimits: Record<string, { maxThickness: number; maxConcentration: number }> = {
    'PC1': { maxThickness: 5.0, maxConcentration: 100 },
    'PC2': { maxThickness: 4.0, maxConcentration: 100 },
    'PC3': { maxThickness: 3.5, maxConcentration: 100 },
    'PC4': { maxThickness: 3.0, maxConcentration: 100 },
    'PC5': { maxThickness: 2.5, maxConcentration: 100 },
    'PC6': { maxThickness: 1.5, maxConcentration: 90 },
    'PC7': { maxThickness: 1.0, maxConcentration: 70 },
  }

  const limits = iceClassLimits[iceClass] || iceClassLimits['PC7']

  // Calculate speed reduction
  let maxSpeed = 12 // knots (open water speed)
  let recommended = 12
  let warning: string | undefined

  if (thickness > limits.maxThickness) {
    maxSpeed = 0
    recommended = 0
    warning = `Ice too thick for ${iceClass}. Max: ${limits.maxThickness}m, Actual: ${thickness.toFixed(1)}m`
  } else if (concentration > limits.maxConcentration) {
    maxSpeed = 3
    recommended = 2
    warning = `Ice concentration too high for ${iceClass}`
  } else if (thickness > 0) {
    // Speed reduction formula
    const thicknessRatio = thickness / limits.maxThickness
    const concentrationRatio = concentration / 100

    maxSpeed = Math.round((12 - thicknessRatio * 7 - concentrationRatio * 3) * 10) / 10
    recommended = Math.round(maxSpeed * 0.8 * 10) / 10

    if (thickness > limits.maxThickness * 0.8) {
      warning = 'Approaching ice thickness limit'
    }
  }

  return {
    maxSpeed: Math.max(0, maxSpeed),
    recommended: Math.max(0, recommended),
    warning,
  }
}

// ────────────────────────────────────────────────────────────────────────────
// USE MOCK OR REAL API
// ────────────────────────────────────────────────────────────────────────────

const USE_MOCK_DATA = true // Set to false when backend is ready

export async function getIceThicknessGrid(
  bounds: MapBounds,
  time?: string
): Promise<IceThicknessGridResponse> {
  if (USE_MOCK_DATA) {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 400))
    return getMockIceThicknessGrid(bounds)
  }

  return fetchIceThicknessGrid(bounds, time)
}
