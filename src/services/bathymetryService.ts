// ============================================================================
// Bathymetry Service - Backend API Integration
// ============================================================================

import { apiRequest } from './api'
import type {
  BathymetryResponse,
  DepthContour,
  MapBounds
} from '../types/api.types'

// ────────────────────────────────────────────────────────────────────────────
// API ENDPOINTS
// ────────────────────────────────────────────────────────────────────────────

/**
 * Fetch bathymetry (depth) contours for a given map bounds
 *
 * Backend API should implement:
 * GET /bathymetry/contours?minLon=30&maxLon=60&minLat=-75&maxLat=-65&depths=-100,-500,-1000,-3000
 *
 * Returns: BathymetryResponse
 */
export async function fetchBathymetryContours(
  bounds: MapBounds,
  depths: number[] = [-100, -500, -1000, -2000, -3000, -4000]
): Promise<BathymetryResponse> {
  const params = new URLSearchParams({
    minLon: bounds.minLon.toString(),
    maxLon: bounds.maxLon.toString(),
    minLat: bounds.minLat.toString(),
    maxLat: bounds.maxLat.toString(),
    depths: depths.join(','),
  })

  return apiRequest<BathymetryResponse>(`/bathymetry/contours?${params}`)
}

// ────────────────────────────────────────────────────────────────────────────
// MOCK DATA (Remove when backend is ready)
// ────────────────────────────────────────────────────────────────────────────

export function getMockBathymetryContours(
  bounds: MapBounds,
  depths: number[] = [-100, -500, -1000, -2000, -3000, -4000]
): BathymetryResponse {
  const contours: DepthContour[] = []

  depths.forEach((depth) => {
    const numPoints = 40
    const coords: [number, number][] = []

    // Generate approximate contour following Antarctic shelf
    for (let i = 0; i <= numPoints; i++) {
      const angle = (i / numPoints) * Math.PI * 2
      const centerLon = (bounds.minLon + bounds.maxLon) / 2
      const centerLat = (bounds.minLat + bounds.maxLat) / 2

      // Radius increases with depth
      const baseRadius = Math.abs(depth) / 500 + 2
      const radius = baseRadius + Math.sin(angle * 3) * 0.5 // irregular shape

      const lon = centerLon + radius * Math.cos(angle)
      const lat = centerLat + radius * Math.sin(angle) * 0.5 // compress latitude

      // Keep within bounds
      if (lon >= bounds.minLon && lon <= bounds.maxLon &&
          lat >= bounds.minLat && lat <= bounds.maxLat) {
        coords.push([lon, lat])
      }
    }

    if (coords.length > 3) {
      contours.push({ depth, coordinates: coords })
    }
  })

  return {
    contours,
    source: 'GEBCO 2023 (Mock)',
    resolution: 500, // meters
    coverage: bounds,
  }
}

// ────────────────────────────────────────────────────────────────────────────
// DEPTH SAFETY CHECKS
// ────────────────────────────────────────────────────────────────────────────

/**
 * Check if water depth is safe for vessel draft
 */
export function isDepthSafe(
  depth: number,
  vesselDraft: number,
  safetyMargin: number = 5 // meters under-keel clearance
): { isSafe: boolean; warning?: string } {
  const requiredDepth = vesselDraft + safetyMargin
  const actualDepth = Math.abs(depth) // depth is negative

  if (actualDepth < requiredDepth) {
    return {
      isSafe: false,
      warning: `Insufficient depth: ${actualDepth.toFixed(1)}m (need ${requiredDepth.toFixed(1)}m)`,
    }
  }

  if (actualDepth < requiredDepth + 5) {
    return {
      isSafe: true,
      warning: `Shallow water: ${actualDepth.toFixed(1)}m depth, ${vesselDraft.toFixed(1)}m draft`,
    }
  }

  return { isSafe: true }
}

/**
 * Get depth color for visualization
 */
export function getDepthColor(depth: number): string {
  const absDepth = Math.abs(depth)

  if (absDepth < 50) return '#d73027' // Very shallow - red
  if (absDepth < 100) return '#fc8d59' // Shallow - orange
  if (absDepth < 500) return '#fee08b' // Medium shallow - yellow
  if (absDepth < 1000) return '#d9ef8b' // Medium - light green
  if (absDepth < 2000) return '#91bfdb' // Deep - light blue
  if (absDepth < 3000) return '#4575b4' // Very deep - blue
  return '#313695' // Abyssal - dark blue
}

// ────────────────────────────────────────────────────────────────────────────
// USE MOCK OR REAL API
// ────────────────────────────────────────────────────────────────────────────

const USE_MOCK_DATA = true // Set to false when backend is ready

export async function getBathymetryContours(
  bounds: MapBounds,
  depths?: number[]
): Promise<BathymetryResponse> {
  if (USE_MOCK_DATA) {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 350))
    return getMockBathymetryContours(bounds, depths)
  }

  return fetchBathymetryContours(bounds, depths)
}
