// ============================================================================
// React Hooks for Map Data Fetching
// ============================================================================

import { useState, useEffect, useCallback } from 'react'
import type {
  WeatherGridResponse,
  IceThicknessGridResponse,
  BathymetryResponse,
  RouteResponse,
  RouteRequest,
  Waypoint,
  MapBounds
} from '../types/api.types'

import { getWeatherGrid } from '../services/weatherService'
import { getIceThicknessGrid } from '../services/iceService'
import { getBathymetryContours } from '../services/bathymetryService'
import { getComputedRoute } from '../services/routeService'

// ────────────────────────────────────────────────────────────────────────────
// useWeatherData Hook
// ────────────────────────────────────────────────────────────────────────────

interface UseWeatherDataOptions {
  bounds: MapBounds
  time?: string
  enabled?: boolean
}

export function useWeatherData({ bounds, time, enabled = true }: UseWeatherDataOptions) {
  const [data, setData] = useState<WeatherGridResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = useCallback(async () => {
    if (!enabled) return

    setLoading(true)
    setError(null)

    try {
      const result = await getWeatherGrid(bounds, time)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch weather data'))
    } finally {
      setLoading(false)
    }
  }, [bounds, time, enabled])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

// ────────────────────────────────────────────────────────────────────────────
// useIceThicknessData Hook
// ────────────────────────────────────────────────────────────────────────────

interface UseIceThicknessOptions {
  bounds: MapBounds
  time?: string
  enabled?: boolean
}

export function useIceThicknessData({ bounds, time, enabled = true }: UseIceThicknessOptions) {
  const [data, setData] = useState<IceThicknessGridResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = useCallback(async () => {
    if (!enabled) return

    setLoading(true)
    setError(null)

    try {
      const result = await getIceThicknessGrid(bounds, time)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch ice thickness data'))
    } finally {
      setLoading(false)
    }
  }, [bounds, time, enabled])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

// ────────────────────────────────────────────────────────────────────────────
// useBathymetryData Hook
// ────────────────────────────────────────────────────────────────────────────

interface UseBathymetryOptions {
  bounds: MapBounds
  depths?: number[]
  enabled?: boolean
}

export function useBathymetryData({ bounds, depths, enabled = true }: UseBathymetryOptions) {
  const [data, setData] = useState<BathymetryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = useCallback(async () => {
    if (!enabled) return

    setLoading(true)
    setError(null)

    try {
      const result = await getBathymetryContours(bounds, depths)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch bathymetry data'))
    } finally {
      setLoading(false)
    }
  }, [bounds, depths, enabled])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

// ────────────────────────────────────────────────────────────────────────────
// useRouteComputation Hook
// ────────────────────────────────────────────────────────────────────────────

export function useRouteComputation() {
  const [data, setData] = useState<RouteResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const computeRoute = useCallback(async (request: RouteRequest) => {
    setLoading(true)
    setError(null)

    try {
      const result = await getComputedRoute(request)
      setData(result)
      return result
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to compute route')
      setError(error)
      throw error
    } finally {
      setLoading(false)
    }
  }, [])

  return { data, loading, error, computeRoute }
}

// ────────────────────────────────────────────────────────────────────────────
// useWaypoints Hook (for interactive waypoint management)
// ────────────────────────────────────────────────────────────────────────────

export function useWaypoints(initialWaypoints: Waypoint[] = []) {
  const [waypoints, setWaypoints] = useState<Waypoint[]>(initialWaypoints)

  const addWaypoint = useCallback((waypoint: Omit<Waypoint, 'id' | 'order'>) => {
    setWaypoints(prev => [
      ...prev,
      {
        ...waypoint,
        id: `wp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        order: prev.length,
      },
    ])
  }, [])

  const updateWaypoint = useCallback((id: string, updates: Partial<Waypoint>) => {
    setWaypoints(prev =>
      prev.map(wp => (wp.id === id ? { ...wp, ...updates } : wp))
    )
  }, [])

  const removeWaypoint = useCallback((id: string) => {
    setWaypoints(prev => {
      const filtered = prev.filter(wp => wp.id !== id)
      // Renumber orders
      return filtered.map((wp, idx) => ({ ...wp, order: idx }))
    })
  }, [])

  const reorderWaypoint = useCallback((id: string, newOrder: number) => {
    setWaypoints(prev => {
      const wp = prev.find(w => w.id === id)
      if (!wp) return prev

      const filtered = prev.filter(w => w.id !== id)
      filtered.splice(newOrder, 0, wp)

      return filtered.map((w, idx) => ({ ...w, order: idx }))
    })
  }, [])

  const clearWaypoints = useCallback(() => {
    setWaypoints([])
  }, [])

  return {
    waypoints,
    addWaypoint,
    updateWaypoint,
    removeWaypoint,
    reorderWaypoint,
    clearWaypoints,
  }
}
