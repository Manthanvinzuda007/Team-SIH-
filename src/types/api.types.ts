// ============================================================================
// Type Definitions for Backend API Integration
// ============================================================================

// ────────────────────────────────────────────────────────────────────────────
// 1. WEATHER DATA TYPES
// ────────────────────────────────────────────────────────────────────────────

export interface WindData {
  longitude: number
  latitude: number
  speed: number // knots
  direction: number // degrees (0-360, 0 = North)
  gust?: number // knots
}

export interface WaveData {
  longitude: number
  latitude: number
  height: number // meters
  period?: number // seconds
  direction?: number // degrees
}

export interface WeatherPoint {
  longitude: number
  latitude: number
  wind: {
    speed: number // knots
    direction: number // degrees
    gust?: number
  }
  waves?: {
    height: number // meters
    period?: number
    direction?: number
  }
  visibility?: number // nautical miles
  temperature?: number // celsius
  pressure?: number // hPa
  timestamp: string // ISO 8601
}

export interface WeatherGridResponse {
  gridPoints: WeatherPoint[]
  timestamp: string
  source: string // "ECMWF" | "NOAA" | "BOM"
  validUntil: string
}

// ────────────────────────────────────────────────────────────────────────────
// 2. ICE THICKNESS DATA TYPES
// ────────────────────────────────────────────────────────────────────────────

export interface IceThicknessPoint {
  longitude: number
  latitude: number
  thickness: number // meters (0 = open water)
  concentration: number // percentage (0-100)
  type: 'first-year' | 'multi-year' | 'fast-ice' | 'pack-ice'
  confidence: number // percentage (0-100)
}

export interface IceThicknessGridResponse {
  gridPoints: IceThicknessPoint[]
  resolution: number // kilometers
  timestamp: string
  source: string // "AMSR2" | "Sentinel-1" | "SMOS"
  validUntil: string
}

// ────────────────────────────────────────────────────────────────────────────
// 3. BATHYMETRY DATA TYPES
// ────────────────────────────────────────────────────────────────────────────

export interface DepthContour {
  depth: number // meters (negative = below sea level)
  coordinates: [number, number][] // [lon, lat][]
}

export interface BathymetryResponse {
  contours: DepthContour[]
  source: string // "GEBCO" | "IBCSO"
  resolution: number // meters
  coverage: {
    minLon: number
    maxLon: number
    minLat: number
    maxLat: number
  }
}

export interface DepthPoint {
  longitude: number
  latitude: number
  depth: number // meters (negative = below sea level)
}

// ────────────────────────────────────────────────────────────────────────────
// 4. WAYPOINT & ROUTE TYPES
// ────────────────────────────────────────────────────────────────────────────

export interface Waypoint {
  id: string
  longitude: number
  latitude: number
  name?: string
  eta?: string // ISO 8601
  notes?: string
  order: number // sequence in route
}

export interface RouteSegment {
  from: Waypoint
  to: Waypoint
  distance: number // nautical miles
  bearing: number // degrees
  duration: number // hours
  riskScore: number // 0-100
}

export interface RouteRequest {
  waypoints: Omit<Waypoint, 'id'>[]
  vesselProfile: {
    iceClass: string // "PC6" | "PC7" | etc
    draft: number // meters
    speed: number // knots
    fuelConsumption?: number // tons/hour
  }
  optimization: 'fastest' | 'safest' | 'balanced'
  departureTime: string // ISO 8601
}

export interface RouteResponse {
  waypoints: Waypoint[]
  segments: RouteSegment[]
  totalDistance: number // nautical miles
  totalDuration: number // hours
  totalFuel?: number // tons
  totalRisk: number // 0-100
  alternativeRoutes?: RouteResponse[]
  warnings: string[]
  computedAt: string // ISO 8601
}

// ────────────────────────────────────────────────────────────────────────────
// 5. VESSEL SAFE SPEED TYPES
// ────────────────────────────────────────────────────────────────────────────

export interface SafeSpeedRequest {
  vesselIceClass: string
  currentPosition: {
    longitude: number
    latitude: number
  }
}

export interface SafeSpeedResponse {
  maxSafeSpeed: number // knots
  recommendedSpeed: number // knots
  iceThickness: number // meters
  iceConcentration: number // percentage
  reason: string
  restrictions: string[]
}

// ────────────────────────────────────────────────────────────────────────────
// 6. MAP BOUNDS & QUERY TYPES
// ────────────────────────────────────────────────────────────────────────────

export interface MapBounds {
  minLon: number
  maxLon: number
  minLat: number
  maxLat: number
}

export interface TimeRange {
  start: string // ISO 8601
  end: string // ISO 8601
}

// ────────────────────────────────────────────────────────────────────────────
// 7. EXPORT TYPES
// ────────────────────────────────────────────────────────────────────────────

export type { }
