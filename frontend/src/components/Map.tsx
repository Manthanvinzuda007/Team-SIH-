import { Fragment, useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Marker, ImageOverlay, useMapEvents, useMap, Rectangle } from 'react-leaflet';
import L from 'leaflet';

// Leaflet default CRS is EPSG:3857 (Web Mercator). There is no polar-stereo tile
// layer in this prototype; overlays are geographic ImageOverlays. Distortion
// increases toward the pole — routing itself is on an EPSG:3031 analysis grid.

const vesselIcon = new L.DivIcon({
  html: `<div style="color:#0ea5e9;font-size:20px;transform:rotate(184deg)">▲</div>`,
  className: '',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

function pinIcon(color: string, glyph: string) {
  return new L.DivIcon({
    html: `<div style="display:flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);box-shadow:0 0 0 2px rgba(2,6,23,0.8)"><span style="transform:rotate(45deg);font-size:11px;color:#020617;font-weight:bold">${glyph}</span></div>`,
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 22],
  });
}
const originIcon = pinIcon('#10b981', 'O');
const destIcon = pinIcon('#f59e0b', 'D');

export type LayerKey =
  | 'seaIce'
  | 'referenceIcebergs'
  | 'sarCandidates'
  | 'predictedIcebergs'
  | 'risk'
  | 'route'
  | 'currents'
  | 'weather'
  | 'bathymetry';

export type PickMode = 'origin' | 'destination' | null;

interface OceanVector {
  lat: number;
  lon: number;
  u_ms: number;
  v_ms: number;
  speed_ms: number;
  speed_knots: number;
}

export interface IcebergPoint {
  id: number;
  name: string;
  lat: number;
  lon: number;
  confidence: number;
  source?: string;
  status?: string;
  category?: string;
}

export interface PredictedTrack {
  iceberg_id: number;
  origin: { lat: number; lon: number };
  points: Array<{ lat: number; lon: number; forecast_hour: number }>;
  confidence_corridor_km: number | null;
}

interface Overlay {
  url: string;
  bounds: [[number, number], [number, number]];
}

interface AntarcticMapProps {
  icebergs?: IcebergPoint[];
  predictedTracks?: PredictedTrack[];
  routes?: Array<{ mode: string; path_points: Array<{ lat: number; lon: number }>; fallback?: boolean }>;
  activeRouteMode?: string | null;
  layers: Record<LayerKey, boolean>;
  iceOverlay?: Overlay | null;
  riskOverlay?: Overlay | null;
  weatherOverlay?: Overlay | null;
  bathymetryOverlay?: Overlay | null;
  oceanHint?: OceanVector[];
  origin?: { lat: number; lon: number } | null;
  destination?: { lat: number; lon: number } | null;
  pickMode?: PickMode;
  onPick?: (lat: number, lon: number) => void;
  onIcebergSelect?: (iceberg: IcebergPoint) => void;
}

/**
 * Render a current vector as a short arrow polyline.
 * Arrow length is proportional to speed (capped for visibility).
 */
function currentArrow(v: OceanVector): { positions: [number, number][]; color: string } {
  const scale = 0.8; // degrees per m/s (visual only — not geophysically meaningful)
  const mag = Math.min(v.speed_ms, 1.5); // cap length
  const dlat = v.v_ms * scale * (mag / Math.max(v.speed_ms, 0.01));
  const dlon = v.u_ms * scale * (mag / Math.max(v.speed_ms, 0.01));
  const endLat = v.lat + dlat;
  const endLon = v.lon + dlon;

  // Color by speed: blue < 0.1 m/s, cyan < 0.3, yellow < 0.6, red >= 0.6
  let color = '#3b82f6'; // blue
  if (v.speed_ms >= 0.6) color = '#ef4444';
  else if (v.speed_ms >= 0.3) color = '#eab308';
  else if (v.speed_ms >= 0.1) color = '#06b6d4';

  return {
    positions: [[v.lat, v.lon], [endLat, endLon]],
    color,
  };
}

function ClickCatcher({ pickMode, onPick }: { pickMode?: PickMode; onPick?: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      if (pickMode && onPick) {
        onPick(Number(e.latlng.lat.toFixed(4)), Number(e.latlng.lng.toFixed(4)));
      }
    },
  });
  return null;
}

function CoordTracker() {
  const [mousePos, setMousePos] = useState<{lat: number; lon: number} | null>(null);
  useMapEvents({
    mousemove(e) {
      setMousePos({ lat: e.latlng.lat, lon: e.latlng.lng });
    },
    mouseout() {
      setMousePos(null);
    }
  });
  return mousePos ? (
    <div style={{position:'absolute', bottom:8, left:8, zIndex:1000}} 
         className="bg-slate-900/90 border border-slate-700 px-2 py-1 rounded text-xs font-mono text-sky-400">
      {mousePos.lat.toFixed(4)}°S {Math.abs(mousePos.lon).toFixed(4)}°{mousePos.lon < 0 ? 'W' : 'E'}
    </div>
  ) : null;
}

/** Forces map to recalculate its size after React finishes layout.
 *  Fixes the "small rectangle" bug when Leaflet initialises inside a flex container. */
function MapResizer() {
  const map = useMap();
  useEffect(() => {
    // Invalidate immediately and after layout settles
    map.invalidateSize();
    const t1 = setTimeout(() => map.invalidateSize(), 100);
    const t2 = setTimeout(() => map.invalidateSize(), 500);
    // Also invalidate on window resize
    const onResize = () => map.invalidateSize();
    window.addEventListener('resize', onResize);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener('resize', onResize);
    };
  }, [map]);
  return null;
}

export type BaseMapStyle = 'osm' | 'satellite' | 'voyager' | 'dark';

const BASEMAPS: Record<BaseMapStyle, { name: string; url: string; attribution: string }> = {
  osm: {
    name: 'Full Color Map',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    name: 'Satellite (Full Color)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
  },
  voyager: {
    name: 'Voyager (Color)',
    url: 'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO, OpenStreetMap',
  },
  dark: {
    name: 'Dark Mode',
    url: 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CARTO, OpenStreetMap',
  },
};

export default function AntarcticMap({
  icebergs = [],
  predictedTracks = [],
  routes = [],
  activeRouteMode = null,
  layers,
  iceOverlay,
  riskOverlay,
  weatherOverlay,
  bathymetryOverlay,
  oceanHint,
  origin,
  destination,
  pickMode = null,
  onPick,
  onIcebergSelect,
}: AntarcticMapProps) {
  const center: L.LatLngTuple = [-67, -45];
  const [activeBasemap, setActiveBasemap] = useState<BaseMapStyle>('osm');

  const routeColors: Record<string, string> = {
    FASTEST: '#facc15',
    SAFEST: '#10b981',
    BALANCED: '#0ea5e9',
    CUSTOM: '#c084fc',
  };

  const referenceIcebergs = icebergs.filter((i) => i.category !== 'SAR_CANDIDATE');
  const sarIcebergs = icebergs.filter((i) => i.category === 'SAR_CANDIDATE');
  const currentTileConfig = BASEMAPS[activeBasemap];

  return (
    <div className="absolute inset-0 h-full w-full">
      {/* Floating Basemap Selector */}
      <div className="absolute top-3 left-3 z-[1000] flex space-x-1 bg-slate-900/90 border border-slate-700 p-1 rounded-lg shadow-lg font-mono text-[10px]">
        {(Object.keys(BASEMAPS) as BaseMapStyle[]).map((key) => (
          <button
            key={key}
            onClick={() => setActiveBasemap(key)}
            className={`px-2 py-1 rounded transition-colors ${
              activeBasemap === key
                ? 'bg-sky-500 text-slate-950 font-bold'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            {BASEMAPS[key].name}
          </button>
        ))}
      </div>

      {pickMode && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[1000] px-3 py-1 rounded text-xs font-mono font-bold bg-sky-500 text-slate-950 shadow">
          Click the map to set {pickMode === 'origin' ? 'ORIGIN' : 'DESTINATION'}
        </div>
      )}
      <MapContainer
        center={center}
        zoom={4}
        minZoom={2}
        maxZoom={16}
        style={{ height: '100%', width: '100%', background: '#0f172a', cursor: pickMode ? 'crosshair' : undefined }}
        zoomControl={false}
      >
        <ClickCatcher pickMode={pickMode} onPick={onPick} />
        <MapResizer />
        <CoordTracker />
        <TileLayer
          key={activeBasemap}
          url={currentTileConfig.url}
          attribution={currentTileConfig.attribution}
          maxZoom={18}
        />


        {/* Bathymetry overlay (render first — lowest z among data layers) */}
        {layers.bathymetry && bathymetryOverlay && (
          <ImageOverlay url={bathymetryOverlay.url} bounds={bathymetryOverlay.bounds} opacity={0.5} />
        )}

        {/* Sea-ice overlay */}
        {layers.seaIce && iceOverlay && (
          <ImageOverlay url={iceOverlay.url} bounds={iceOverlay.bounds} opacity={0.65} />
        )}

        {/* Weather (wind speed) overlay */}
        {layers.weather && weatherOverlay && (
          <ImageOverlay url={weatherOverlay.url} bounds={weatherOverlay.bounds} opacity={0.4} />
        )}

        {/* Risk overlay */}
        {layers.risk && riskOverlay && (
          <ImageOverlay url={riskOverlay.url} bounds={riskOverlay.bounds} opacity={0.45} />
        )}

        {/* Ocean current vectors */}
        {layers.currents && oceanHint && oceanHint.map((v, i) => {
          const arrow = currentArrow(v);
          return (
            <Polyline
              key={`current-${i}`}
              positions={arrow.positions}
              color={arrow.color}
              weight={1.5}
              opacity={0.7}
            >
              <Popup>
                <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                  <strong>Ocean Current</strong><br/>
                  Speed: {v.speed_knots.toFixed(2)} kn ({v.speed_ms.toFixed(3)} m/s)<br/>
                  U: {v.u_ms.toFixed(3)} m/s · V: {v.v_ms.toFixed(3)} m/s<br/>
                  Source: GLORYS12 Jun 2026 (historical)
                </div>
              </Popup>
            </Polyline>
          );
        })}

        {/* Vessel marker (static demo position) */}
        <Marker position={[-72.25, -65.7]} icon={vesselIcon}>
          <Popup>
            <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
              <strong>R/V Bharathi</strong><br/>
              Static demo position — not live AIS
            </div>
          </Popup>
        </Marker>

        {/* Origin / destination markers */}
        {origin && (
          <Marker position={[origin.lat, origin.lon]} icon={originIcon}>
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                <strong>Origin</strong><br/>{origin.lat.toFixed(3)}°, {origin.lon.toFixed(3)}°
              </div>
            </Popup>
          </Marker>
        )}
        {destination && (
          <Marker position={[destination.lat, destination.lon]} icon={destIcon}>
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                <strong>Destination</strong><br/>{destination.lat.toFixed(3)}°, {destination.lon.toFixed(3)}°
              </div>
            </Popup>
          </Marker>
        )}

        {/* Route polylines */}
        {layers.route && routes.map((route) => {
          const isActive = activeRouteMode ? route.mode === activeRouteMode : route.mode === 'BALANCED';
          return (
            <Polyline
              key={route.mode}
              positions={route.path_points.map(p => [p.lat, p.lon] as L.LatLngTuple)}
              color={routeColors[route.mode] || '#0ea5e9'}
              weight={isActive ? 5 : 3}
              dashArray={route.fallback ? '4, 8' : undefined}
              opacity={route.fallback ? 0.5 : isActive ? 1.0 : 0.6}
            >
              <Popup>
                <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                  <strong style={{ color: routeColors[route.mode] || '#0ea5e9' }}>{route.mode} ROUTE</strong><br/>
                  Distance: {route.distance_nm} NM · ETA: {route.estimated_time_hours}h<br/>
                  Safety: {route.safety_score}% · Risk: {route.risk_score}<br/>
                  {route.fallback && <span style={{ color: '#f59e0b' }}>⚠️ Fallback Geodesic Path</span>}
                </div>
              </Popup>
            </Polyline>
          );
        })}

        {/* Reference / validated icebergs (BYU_MERS) */}
        {layers.referenceIcebergs && referenceIcebergs.map((berg) => (
          <CircleMarker
            key={`ref-${berg.id}`}
            center={[berg.lat, berg.lon]}
            radius={4}
            color="#0ea5e9"
            fillColor="#0ea5e9"
            fillOpacity={0.55}
            weight={1}
            eventHandlers={onIcebergSelect ? { click: () => onIcebergSelect(berg) } : undefined}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                <strong>{berg.name}</strong><br/>
                {berg.lat.toFixed(2)}°, {berg.lon.toFixed(2)}°<br/>
                Reference / validated track (BYU MERS)<br/>
                Conf: {((berg.confidence || 0) * 100).toFixed(0)}%
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* SAR candidate detections (Sentinel-1 CFAR) — visually distinct, never labelled "confirmed" */}
        {layers.sarCandidates && sarIcebergs.map((berg) => (
          <CircleMarker
            key={`sar-${berg.id}`}
            center={[berg.lat, berg.lon]}
            radius={5}
            color="#f59e0b"
            fillColor="#f59e0b"
            fillOpacity={0.35}
            weight={1.5}
            dashArray="2,2"
            eventHandlers={onIcebergSelect ? { click: () => onIcebergSelect(berg) } : undefined}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                <strong>{berg.name}</strong><br/>
                {berg.lat.toFixed(2)}°, {berg.lon.toFixed(2)}°<br/>
                <span style={{ color: '#f59e0b' }}>SAR CANDIDATE — not a confirmed iceberg</span><br/>
                Sentinel-1 CFAR detection, conf {((berg.confidence || 0) * 100).toFixed(0)}%
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Predicted iceberg positions (LSTM forecast) */}
        {layers.predictedIcebergs && predictedTracks.map((track) => (
          <Fragment key={`pred-${track.iceberg_id}`}>
            <Polyline
              positions={[
                [track.origin.lat, track.origin.lon] as L.LatLngTuple,
                ...track.points.map(p => [p.lat, p.lon] as L.LatLngTuple),
              ]}
              color="#c084fc"
              weight={1.5}
              dashArray="1,6"
              opacity={0.8}
            />
            {track.points.map((p, idx) => (
              <CircleMarker
                key={`pred-pt-${track.iceberg_id}-${idx}`}
                center={[p.lat, p.lon]}
                radius={4}
                color="#c084fc"
                fillColor="#a855f7"
                fillOpacity={0.7}
                weight={1}
              >
                <Popup>
                  <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                    <strong>Predicted position</strong><br/>
                    +{p.forecast_hour}h · {p.lat.toFixed(2)}°, {p.lon.toFixed(2)}°<br/>
                    LSTM forecast — model estimate, not guaranteed<br/>
                    {track.confidence_corridor_km != null && (
                      <>Uncertainty ≈ {track.confidence_corridor_km.toFixed(1)} km</>
                    )}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </Fragment>
        ))}

        {/* Legend */}
        <div className="leaflet-bottom leaflet-right" style={{ position: 'absolute', bottom: 10, right: 10, zIndex: 1000 }}>
          <div style={{ background: 'rgba(15,23,42,0.9)', padding: '8px 10px', borderRadius: 4, fontSize: 10, fontFamily: 'monospace', color: '#94a3b8', lineHeight: 1.6 }}>
            <div style={{ fontWeight: 'bold', marginBottom: 3, color: '#f1f5f9' }}>IAVNS DOMAIN & LEGEND</div>
            <div style={{ color: '#38bdf8', marginBottom: 4, fontSize: 9 }}>🌐 Analysis Domain: 60°S–75°S, 10°W–80°W</div>
            <div><span style={{ color: '#0ea5e9' }}>●</span> Reference / validated (BYU MERS)</div>
            <div><span style={{ color: '#f59e0b' }}>◆</span> SAR candidate (Sentinel-1 CFAR, unconfirmed)</div>
            <div><span style={{ color: '#a855f7' }}>◆</span> Predicted position (LSTM forecast)</div>
          </div>
        </div>

        {/* Current speed legend */}
        {layers.currents && oceanHint && oceanHint.length > 0 && (
          <div className="leaflet-bottom leaflet-left" style={{ position: 'absolute', bottom: 10, left: 10, zIndex: 1000 }}>
            <div style={{ background: 'rgba(15,23,42,0.85)', padding: '6px 10px', borderRadius: 4, fontSize: 10, fontFamily: 'monospace', color: '#94a3b8' }}>
              <div style={{ fontWeight: 'bold', marginBottom: 3 }}>CURRENT SPEED</div>
              <div><span style={{ color: '#3b82f6' }}>━</span> &lt;0.1 kn</div>
              <div><span style={{ color: '#06b6d4' }}>━</span> 0.1–0.3 kn</div>
              <div><span style={{ color: '#eab308' }}>━</span> 0.3–0.6 kn</div>
              <div><span style={{ color: '#ef4444' }}>━</span> &gt;0.6 kn</div>
              <div style={{ marginTop: 3, fontSize: 9, color: '#64748b' }}>GLORYS Jun 2026 (historical)</div>
            </div>
          </div>
        )}
      </MapContainer>
    </div>
  );
}
