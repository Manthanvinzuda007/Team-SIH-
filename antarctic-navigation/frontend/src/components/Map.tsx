import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Marker, ImageOverlay } from 'react-leaflet';
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

export type LayerKey = 'ice' | 'icebergs' | 'risk' | 'route' | 'currents';

interface OceanVector {
  lat: number;
  lon: number;
  u_ms: number;
  v_ms: number;
  speed_ms: number;
  speed_knots: number;
}

interface AntarcticMapProps {
  icebergs?: Array<{id: number; name: string; lat: number; lon: number; confidence: number; source?: string; status?: string}>;
  routes?: Array<{mode: string; path_points: Array<{lat: number; lon: number}>; fallback?: boolean}>;
  layers: Record<LayerKey, boolean>;
  iceOverlay?: { url: string; bounds: [[number, number], [number, number]] } | null;
  riskOverlay?: { url: string; bounds: [[number, number], [number, number]] } | null;
  oceanHint?: OceanVector[];
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

export default function AntarcticMap({
  icebergs = [],
  routes = [],
  layers,
  iceOverlay,
  riskOverlay,
  oceanHint,
}: AntarcticMapProps) {
  const center: L.LatLngTuple = [-67, -45];

  const routeColors: Record<string, string> = {
    FASTEST: '#facc15',
    SAFEST: '#10b981',
    BALANCED: '#ffffff',
  };

  return (
    <div className="absolute inset-0 h-full w-full">
      <MapContainer
        center={center}
        zoom={4}
        minZoom={3}
        maxZoom={8}
        style={{ height: '100%', width: '100%', background: '#0f172a' }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />

        {/* Sea-ice overlay */}
        {layers.ice && iceOverlay && (
          <ImageOverlay url={iceOverlay.url} bounds={iceOverlay.bounds} opacity={0.65} />
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
              <strong>R/V POLARIS</strong><br/>
              Static demo position — not live AIS
            </div>
          </Popup>
        </Marker>

        {/* Route polylines */}
        {layers.route && routes.map((route) => (
          <Polyline
            key={route.mode}
            positions={route.path_points.map(p => [p.lat, p.lon] as L.LatLngTuple)}
            color={routeColors[route.mode] || '#888'}
            weight={route.mode === 'BALANCED' ? 3 : 2}
            dashArray={route.fallback ? '4, 8' : route.mode === 'FASTEST' ? '8, 8' : undefined}
            opacity={route.fallback ? 0.4 : route.mode === 'BALANCED' ? 1 : 0.7}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                <strong>{route.mode}</strong>
                {route.fallback && <span style={{ color: '#f59e0b' }}> (FALLBACK)</span>}
              </div>
            </Popup>
          </Polyline>
        ))}

        {/* Iceberg markers */}
        {layers.icebergs && icebergs.map((berg) => (
          <CircleMarker
            key={berg.id}
            center={[berg.lat, berg.lon]}
            radius={berg.source === 'S1_CFAR' ? 5 : 4}
            color={berg.source === 'S1_CFAR' ? '#f59e0b' : '#0ea5e9'}
            fillColor={berg.source === 'S1_CFAR' ? '#f59e0b' : '#0ea5e9'}
            fillOpacity={0.45}
            weight={1}
          >
            <Popup>
              <div style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                <strong>{berg.name}</strong><br/>
                {berg.lat.toFixed(2)}°, {berg.lon.toFixed(2)}°<br/>
                Source: {berg.source || '?'} | {berg.status}<br/>
                Conf: {((berg.confidence || 0) * 100).toFixed(0)}%
              </div>
            </Popup>
          </CircleMarker>
        ))}

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
