// ============================================================================
// Route & Waypoint Service - Backend API Integration
// ============================================================================

import { apiRequest } from './api'
import type {
  Waypoint,
  RouteRequest,
  RouteResponse,
  RouteSegment
} from '../types/api.types'

// ────────────────────────────────────────────────────────────────────────────
// API ENDPOINTS
// ────────────────────────────────────────────────────────────────────────────

/**
 * Compute optimized route through waypoints
 *
 * Backend API should implement:
 * POST /route/compute
 * Body: RouteRequest
 *
 * Returns: RouteResponse
 */
export async function computeRoute(request: RouteRequest): Promise<RouteResponse> {
  return apiRequest<RouteResponse>('/route/compute', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

/**
 * Validate waypoint (check for hazards)
 *
 * Backend API:
 * POST /route/validate-waypoint
 * Body: { longitude: number, latitude: number, vesselDraft: number }
 */
export async function validateWaypoint(
  lon: number,
  lat: number,
  vesselDraft: number
): Promise<{ valid: boolean; warnings: string[] }> {
  return apiRequest('/route/validate-waypoint', {
    method: 'POST',
    body: JSON.stringify({ longitude: lon, latitude: lat, vesselDraft }),
  })
}

// ────────────────────────────────────────────────────────────────────────────
// HELPER FUNCTIONS
// ────────────────────────────────────────────────────────────────────────────

/**
 * Calculate distance between two points using Haversine formula
 * Returns distance in nautical miles
 */
export function calculateDistance(
  lon1: number,
  lat1: number,
  lon2: number,
  lat2: number
): number {
  const R = 3440.065 // Earth radius in nautical miles
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) *
    Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

/**
 * Calculate bearing from point 1 to point 2
 * Returns bearing in degrees (0-360)
 */
export function calculateBearing(
  lon1: number,
  lat1: number,
  lon2: number,
  lat2: number
): number {
  const dLon = (lon2 - lon1) * Math.PI / 180
  const lat1Rad = lat1 * Math.PI / 180
  const lat2Rad = lat2 * Math.PI / 180

  const y = Math.sin(dLon) * Math.cos(lat2Rad)
  const x =
    Math.cos(lat1Rad) * Math.sin(lat2Rad) -
    Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon)

  let bearing = Math.atan2(y, x) * 180 / Math.PI
  bearing = (bearing + 360) % 360

  return bearing
}

/**
 * Generate unique waypoint ID
 */
export function generateWaypointId(): string {
  return `wp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// ────────────────────────────────────────────────────────────────────────────
// MOCK ROUTE COMPUTATION (Remove when backend is ready)
// ────────────────────────────────────────────────────────────────────────────

export function computeMockRoute(request: RouteRequest): RouteResponse {
  const waypoints: Waypoint[] = request.waypoints.map((wp, idx) => ({
    ...wp,
    id: generateWaypointId(),
    order: idx,
  }))

  const segments: RouteSegment[] = []
  let totalDistance = 0
  let totalDuration = 0
  let departureTime = new Date(request.departureTime)

  for (let i = 0; i < waypoints.length - 1; i++) {
    const from = waypoints[i]
    const to = waypoints[i + 1]

    const distance = calculateDistance(
      from.longitude,
      from.latitude,
      to.longitude,
      to.latitude
    )
    const bearing = calculateBearing(
      from.longitude,
      from.latitude,
      to.longitude,
      to.latitude
    )

    // Simple risk calculation (would be more complex in backend)
    const riskScore = Math.round(Math.random() * 40 + 10) // 10-50 range

    const speed = request.vesselProfile.speed
    const duration = distance / speed

    const segmentEta = new Date(departureTime.getTime() + duration * 3600000)
    to.eta = segmentEta.toISOString()

    segments.push({
      from,
      to,
      distance: Math.round(distance * 10) / 10,
      bearing: Math.round(bearing),
      duration: Math.round(duration * 10) / 10,
      riskScore,
    })

    totalDistance += distance
    totalDuration += duration
    departureTime = segmentEta
  }

  const totalRisk = Math.round(
    segments.reduce((sum, seg) => sum + seg.riskScore, 0) / segments.length
  )

  const warnings: string[] = []
  if (totalRisk > 50) {
    warnings.push('High risk route - consider alternatives')
  }
  if (totalDistance > 500) {
    warnings.push('Long route - ensure adequate fuel reserves')
  }

  return {
    waypoints,
    segments,
    totalDistance: Math.round(totalDistance * 10) / 10,
    totalDuration: Math.round(totalDuration * 10) / 10,
    totalFuel: request.vesselProfile.fuelConsumption
      ? Math.round(totalDuration * request.vesselProfile.fuelConsumption * 10) / 10
      : undefined,
    totalRisk,
    warnings,
    computedAt: new Date().toISOString(),
  }
}

// ────────────────────────────────────────────────────────────────────────────
// USE MOCK OR REAL API
// ────────────────────────────────────────────────────────────────────────────

const USE_MOCK_DATA = true // Set to false when backend is ready

export async function getComputedRoute(request: RouteRequest): Promise<RouteResponse> {
  if (USE_MOCK_DATA) {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 600))
    return computeMockRoute(request)
  }

  return computeRoute(request)
}

export async function checkWaypointValidity(
  lon: number,
  lat: number,
  vesselDraft: number
): Promise<{ valid: boolean; warnings: string[] }> {
  if (USE_MOCK_DATA) {
    // Simple mock validation
    await new Promise(resolve => setTimeout(resolve, 100))

    const warnings: string[] = []
    let valid = true

    // Check if in danger zone (simplified)
    if (lat > -65) {
      warnings.push('Outside normal operating area')
    }

    return { valid, warnings }
  }

  return validateWaypoint(lon, lat, vesselDraft)
}
