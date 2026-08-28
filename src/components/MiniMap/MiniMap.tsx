import { useEffect, useRef, memo } from 'react'
import proj4 from 'proj4'
import 'ol/ol.css'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import VectorSource from 'ol/source/Vector'
import XYZ from 'ol/source/XYZ'
import TileGrid from 'ol/tilegrid/TileGrid'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import Polygon from 'ol/geom/Polygon'
import Style from 'ol/style/Style'
import Fill from 'ol/style/Fill'
import Stroke from 'ol/style/Stroke'
import CircleStyle from 'ol/style/Circle'
import { register } from 'ol/proj/proj4'
import { fromLonLat } from 'ol/proj'
import styles from './MiniMap.module.css'

// ── Projection (safe to call multiple times) ──────────────────────────────────
proj4.defs(
  'EPSG:3031',
  '+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs'
)
register(proj4)

// ── ArcGIS Antarctic tile grid ────────────────────────────────────────────────
const ARCGIS_EXTENT: [number, number, number, number] = [
  -33699550.99203, -33699550.99203, 33699550.99203, 33699550.99203,
]
const arcgisResolutions = Array.from({ length: 16 }, (_, i) => 238810.813354 / 2 ** i)

const toProj = (lon: number, lat: number) => fromLonLat([lon, lat], 'EPSG:3031')

// ── Ice edge config per frame ─────────────────────────────────────────────────
// edgeLat: northern boundary of simulated ice pack
// opacity: how opaque the ice overlay is
// In production, replace with real raster tiles from backend
const ICE_FRAME_CONFIG: Record<string, { edgeLat: number; opacity: number }> = {
  current: { edgeLat: -68.0, opacity: 0.42 },
  '6h':    { edgeLat: -67.7, opacity: 0.38 },
  '12h':   { edgeLat: -67.4, opacity: 0.34 },
  '24h':   { edgeLat: -68.0, opacity: 0.0  }, // unavailable — no overlay
}

// ── Build ice concentration polygon ──────────────────────────────────────────
function buildIceFeature(edgeLat: number, opacity: number): Feature {
  // Rough ice polygon visible in the mini map view area (lon 30–65, lat -65 to -78)
  // Northern edge varies by frame to simulate ice drift/growth
  // Backend: swap this for real NSIDC/AMSR2 raster layer
  const ringLonLat: [number, number][] = [
    [30, edgeLat],
    [35, edgeLat - 0.4],
    [40, edgeLat - 0.6],
    [45, edgeLat - 0.3],
    [50, edgeLat - 0.5],
    [55, edgeLat - 0.2],
    [60, edgeLat - 0.4],
    [65, edgeLat - 0.1],
    [65, -78],
    [30, -78],
    [30, edgeLat],
  ]

  const ring = ringLonLat.map(([lon, lat]) => toProj(lon, lat))

  const feature = new Feature({ geometry: new Polygon([ring]) })

  const alpha = Math.round(opacity * 255)
    .toString(16)
    .padStart(2, '0')

  feature.setStyle(
    new Style({
      fill: new Fill({ color: `#c0ddf0${alpha}` }),
      stroke: new Stroke({ color: `#90c0e0${alpha}`, width: 0.8 }),
    })
  )
  return feature
}

// ── Ship dot ──────────────────────────────────────────────────────────────────
function buildShipFeature(lon: number, lat: number): Feature {
  const feature = new Feature({ geometry: new Point(toProj(lon, lat)) })
  feature.setStyle(
    new Style({
      image: new CircleStyle({
        radius: 3,
        fill: new Fill({ color: '#f59e0b' }),
        stroke: new Stroke({ color: '#1a1206', width: 1 }),
      }),
    })
  )
  return feature
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface MiniMapProps {
  frameId: string          // 'current' | '6h' | '12h' | '24h'
  label: string            // display label
  available: boolean       // false = UNAVAILABLE overlay
  vesselLon?: number       // backend: real vessel lon
  vesselLat?: number       // backend: real vessel lat
}

// ── Component ─────────────────────────────────────────────────────────────────
function MiniMapImpl({
  frameId,
  available,
  vesselLon = 45.315,
  vesselLat = -70.359,
}: MiniMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<Map | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const config = ICE_FRAME_CONFIG[frameId] ?? ICE_FRAME_CONFIG.current

    // Basemap
    const basemap = new TileLayer({
      source: new XYZ({
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Polar/Antarctic_Imagery/MapServer/tile/{z}/{y}/{x}',
        projection: 'EPSG:3031',
        tileGrid: new TileGrid({
          extent: ARCGIS_EXTENT,
          resolutions: arcgisResolutions,
        }),
        crossOrigin: 'anonymous',
        wrapX: false,
      }),
    })

    // Ice overlay
    const iceSource = new VectorSource()
    if (available && config.opacity > 0) {
      iceSource.addFeature(buildIceFeature(config.edgeLat, config.opacity))
    }

    // Ship
    const shipSource = new VectorSource()
    shipSource.addFeature(buildShipFeature(vesselLon, vesselLat))

    const map = new Map({
      target: containerRef.current,
      layers: [
        basemap,
        new VectorLayer({ source: iceSource }),
        new VectorLayer({ source: shipSource }),
      ],
      view: new View({
        projection: 'EPSG:3031',
        center: toProj(vesselLon, vesselLat),
        zoom: 3,
        enableRotation: false,
        minZoom: 3,
        maxZoom: 3, // locked — mini map is static
      }),
      controls: [],   // no zoom buttons, no scale bar
      interactions: [], // fully static — no drag, no scroll
    })

    mapRef.current = map

    return () => {
      map.setTarget(undefined)
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frameId, available, vesselLon, vesselLat])

  return (
    <div className={styles.wrapper}>
      <div ref={containerRef} className={styles.map} />
      {!available && (
        <div className={styles.unavailableOverlay}>
          <span className={styles.unavailableText}>UNAVAILABLE</span>
        </div>
      )}
    </div>
  )
}

export const MiniMap = memo(MiniMapImpl)
export default MiniMap