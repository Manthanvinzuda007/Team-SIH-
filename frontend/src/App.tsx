import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity, Anchor, Navigation, Thermometer, Layers, AlertTriangle, Wifi, WifiOff,
  Crosshair, MapPin, Info, Gauge, SlidersHorizontal, Menu, X, ChevronRight,
  Sliders, Eye, Compass, ShieldAlert, CheckCircle2, ChevronUp, ChevronDown
} from 'lucide-react';

import AntarcticMap, { LayerKey, PickMode, IcebergPoint, PredictedTrack } from './components/Map';
import { usePollingApi } from './hooks/useApi';
import { useDemoPollingApi, getDemoRoutes } from './hooks/useDemoApi';

type RouteMode = 'FASTEST' | 'SAFEST' | 'BALANCED' | 'CUSTOM';
const FORECAST_HORIZONS = [24, 72, 168] as const;
type ForecastHorizon = typeof FORECAST_HORIZONS[number];

const RISK_COMPONENTS: Array<{ key: string; label: string; availabilityKey?: string }> = [
  { key: 'sea_ice', label: 'Sea Ice', availabilityKey: 'sea_ice' },
  { key: 'iceberg_total', label: 'Iceberg', availabilityKey: 'iceberg_proximity' },
  { key: 'weather', label: 'Weather', availabilityKey: 'weather' },
  { key: 'bathymetry', label: 'Bathymetry', availabilityKey: 'bathymetry' },
  { key: 'current', label: 'Current', availabilityKey: 'ocean_currents' },
];

function friendlyApiError(label: string, err: Error | null): string | null {
  if (!err) return null;
  if (/503/.test(err.message)) {
    return `${label} unavailable. Route remains available using the latest valid state.`;
  }
  if (/404/.test(err.message)) {
    return `${label} not found.`;
  }
  return `${label} unavailable — ${err.message}`;
}

function DataChip({ label, value, tone }: { label: string; value: string; tone: 'ok' | 'warn' | 'bad' | 'muted' }) {
  const toneClass = {
    ok: 'text-green-400 border-green-800/80 bg-green-950/50',
    warn: 'text-yellow-400 border-yellow-800/80 bg-yellow-950/50',
    bad: 'text-red-400 border-red-800/80 bg-red-950/50',
    muted: 'text-slate-400 border-slate-700 bg-slate-900/80',
  }[tone];
  return (
    <div className={`px-2 py-0.5 rounded-full border text-[10px] font-mono font-semibold ${toneClass}`}>
      {label}: {value}
    </div>
  );
}

function LoadingDots({ text }: { text: string }) {
  return (
    <div className="p-3 text-xs font-mono text-slate-400 flex items-center space-x-2">
      <div className="flex space-x-1">
        <div className="w-1.5 h-1.5 bg-sky-400 rounded-full animate-bounce" style={{animationDelay:'0ms'}} />
        <div className="w-1.5 h-1.5 bg-sky-400 rounded-full animate-bounce" style={{animationDelay:'150ms'}} />
        <div className="w-1.5 h-1.5 bg-sky-400 rounded-full animate-bounce" style={{animationDelay:'300ms'}} />
      </div>
      <span>{text}</span>
    </div>
  );
}

function App() {
  const [demoMode, setDemoMode] = useState(false);
  const healthFailureCount = useRef(0);

  // Layout UI State (Google Maps Style Drawer & Floating Popups)
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [menuTab, setMenuTab] = useState<'layers' | 'route' | 'vessel' | 'status'>('layers');
  const [showRiskDetails, setShowRiskDetails] = useState(false);

  // Live UTC clock
  const [currentTime, setCurrentTime] = useState(new Date().toISOString());
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date().toISOString()), 1000);
    return () => clearInterval(timer);
  }, []);

  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    seaIce: true,
    referenceIcebergs: true,
    sarCandidates: true,
    predictedIcebergs: false,
    risk: true,
    route: true,
    currents: false,
    weather: true,
    bathymetry: false,
  });

  const [origin, setOrigin] = useState({ lat: -63.5, lon: -60.0 });
  const [dest, setDest] = useState({ lat: -68.0, lon: -40.0 });
  const [pickMode, setPickMode] = useState<PickMode>(null);
  const [iceForecastHour, setIceForecastHour] = useState(24);
  const [forecastHorizon, setForecastHorizon] = useState<ForecastHorizon>(24);

  const [routeMode, setRouteMode] = useState<RouteMode>('BALANCED');
  const [customWeights, setCustomWeights] = useState({ distance: 1.0, safety: 0.5, fuel: 0.3, current: 0.2 });
  const [activeRouteMode, setActiveRouteMode] = useState<string | null>(null);

  const [vessel, setVessel] = useState({
    iceClass: 'PC5',
    draft: 6.15,
    maxSpeed: 15.0,
    icebreakingCapable: true,
    dedicatedIcebreaker: false,
    name: 'R/V Bharathi'
  });

  const [selectedIceberg, setSelectedIceberg] = useState<IcebergPoint | null>(null);
  const [trajectoryCache, setTrajectoryCache] = useState<Record<number, any>>({});
  const trajectoryLoading = useRef<Set<number>>(new Set());

  // API polling
  const liveIcebergs    = usePollingApi<any>('/icebergs?limit=500', 60000);
  const demoIcebergs    = useDemoPollingApi<any>('/icebergs?limit=500', 60000);
  const liveStatus      = usePollingApi<any>('/data-status', 60000);
  const demoStatus      = useDemoPollingApi<any>('/data-status', 60000);
  const liveHealth      = usePollingApi<any>('/health', 30000);
  const demoHealth      = useDemoPollingApi<any>('/health', 30000);
  const liveMl          = usePollingApi<any>('/ml/status', 60000);
  const demoMl          = useDemoPollingApi<any>('/ml/status', 60000);
  const liveRisk        = usePollingApi<any>(`/risk-map?forecast_horizon_hours=${forecastHorizon}`, 120000);
  const demoRisk        = useDemoPollingApi<any>(`/risk-map?forecast_horizon_hours=${forecastHorizon}`, 120000);
  const liveIce         = usePollingApi<any>('/sea-ice/current', 120000);
  const demoIce         = useDemoPollingApi<any>('/sea-ice/current', 120000);
  const liveForecast    = usePollingApi<any>(`/sea-ice/forecast?hours=${[6,12,18,24,30,36,42,48].join(',')}`, 120000);
  const demoForecast    = useDemoPollingApi<any>(`/sea-ice/forecast?hours=${[6,12,18,24,30,36,42,48].join(',')}`, 120000);
  const liveOcean       = usePollingApi<any>('/ocean?subsample=10', 120000);
  const demoOcean       = useDemoPollingApi<any>('/ocean?subsample=10', 120000);
  const liveWeather     = usePollingApi<any>('/weather', 120000);
  const demoWeather     = useDemoPollingApi<any>('/weather', 120000);
  const liveBathy       = usePollingApi<any>('/bathymetry', 300000);
  const demoBathy       = useDemoPollingApi<any>('/bathymetry', 300000);

  const pick = <T,>(live: { data: T | null; isLoading: boolean; error: Error | null }, demo: { data: T | null; isLoading: boolean; error: Error | null }) =>
    demoMode ? demo : live;

  const { data: icebergsRaw, isLoading: icebergsLoading, error: icebergsError } = pick(liveIcebergs, demoIcebergs);
  const { data: statusData }                                                     = pick(liveStatus, demoStatus);
  const { data: healthData, error: healthError }                                 = pick(liveHealth, demoHealth);
  const { data: mlStatus, error: mlError }                                       = pick(liveMl, demoMl);
  const { data: riskData, error: riskError }                                     = pick(liveRisk, demoRisk);
  const { data: iceData, error: iceError }                                       = pick(liveIce, demoIce);
  const { data: forecastData }                                                   = pick(liveForecast, demoForecast);
  const { data: oceanData, error: oceanError }                                   = pick(liveOcean, demoOcean);
  const { data: weatherData, error: weatherError }                               = pick(liveWeather, demoWeather);
  const { data: bathyData, error: bathyError }                                   = pick(liveBathy, demoBathy);

  useEffect(() => {
    if (healthError) {
      healthFailureCount.current++;
      if (healthFailureCount.current >= 3 && !demoMode) {
        setDemoMode(true);
      }
    } else {
      healthFailureCount.current = 0;
    }
  }, [healthError, demoMode]);

  const isOffline = !!healthError;
  const isPipelineReady = !!(iceData || riskData);

  // Route computation
  const [routes, setRoutes] = useState<any[]>([]);
  const [routing, setRouting] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  const computeRoute = useCallback(async () => {
    setRouting(true);
    setRouteError(null);
    try {
      if (demoMode) {
        await new Promise(r => setTimeout(r, 1500));
        const data = getDemoRoutes();
        setRoutes(data.routes || []);
        setActiveRouteMode('BALANCED');
      } else {
        const body: Record<string, any> = {
          origin,
          destination: dest,
          departure_time: new Date().toISOString(),
          vessel_config: {
            ice_class: vessel.iceClass,
            draft_m: vessel.draft,
            max_speed_knots: vessel.maxSpeed,
            icebreaking_capable: vessel.icebreakingCapable,
            dedicated_icebreaker: vessel.dedicatedIcebreaker,
          },
        };
        if (routeMode === 'CUSTOM') {
          body.mode = 'CUSTOM';
          body.distance_weight = customWeights.distance;
          body.safety_weight = customWeights.safety;
          body.fuel_weight = customWeights.fuel;
          body.current_weight = customWeights.current;
        }
        const res = await fetch('/api/routes/optimize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ message: `HTTP ${res.status}` }));
          throw new Error(err.message || err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        const gotRoutes = data.routes || [];
        setRoutes(gotRoutes);
        setActiveRouteMode(
          gotRoutes.find((r: any) => r.mode === routeMode)?.mode || gotRoutes[0]?.mode || null
        );
        if (gotRoutes.length > 0 && gotRoutes.every((r: any) => r.fallback)) {
          setRouteError('No safe route found for the selected vessel and constraints. Showing fallback geodesic route(s) only.');
        }
      }
    } catch (e: any) {
      setRouteError(e.message || 'Route computation failed');
      setRoutes([]);
    } finally {
      setRouting(false);
    }
  }, [origin, dest, vessel, routeMode, customWeights, demoMode]);

  // Auto-compute route on initial load or when origin/destination change
  useEffect(() => {
    computeRoute();
  }, [origin, dest, vessel.iceClass, demoMode]);

  const handleMapPick = useCallback((lat: number, lon: number) => {
    if (pickMode === 'origin') setOrigin({ lat, lon });
    else if (pickMode === 'destination') setDest({ lat, lon });
    setPickMode(null);
  }, [pickMode]);

  const fetchTrajectory = useCallback(async (id: number) => {
    if (trajectoryCache[id] || trajectoryLoading.current.has(id)) return;
    trajectoryLoading.current.add(id);
    try {
      if (demoMode) {
        await new Promise(r => setTimeout(r, 600));
        const data = await import('./data/demoData').then(m => m.DEMO_TRAJECTORY_1);
        if (id === 1) setTrajectoryCache(prev => ({ ...prev, [id]: data }));
        return;
      }
      const res = await fetch(`/api/icebergs/${id}/trajectory`);
      if (res.ok) {
        const data = await res.json();
        setTrajectoryCache((prev) => ({ ...prev, [id]: data }));
      }
    } catch {
    } finally {
      trajectoryLoading.current.delete(id);
    }
  }, [trajectoryCache, demoMode]);

  const handleIcebergSelect = useCallback((berg: IcebergPoint) => {
    setSelectedIceberg(berg);
    fetchTrajectory(berg.id);
  }, [fetchTrajectory]);

  const mapIcebergs: IcebergPoint[] = useMemo(() => {
    const raw = icebergsRaw?.icebergs || icebergsRaw;
    return Array.isArray(raw) ? raw : [];
  }, [icebergsRaw]);

  const activeTrajectory = useMemo(() => {
    if (!selectedIceberg) return null;
    return trajectoryCache[selectedIceberg.id] || null;
  }, [selectedIceberg, trajectoryCache]);

  const predictedTracks = useMemo(() => {
    if (!layers.predictedIcebergs || !activeTrajectory?.predicted_points) return [];
    return [{
      iceberg_id: activeTrajectory.iceberg_id,
      predicted_points: activeTrajectory.predicted_points,
    }];
  }, [layers.predictedIcebergs, activeTrajectory]);

  const datasets = useMemo(() => statusData?.datasets || [], [statusData]);
  const backtest = useMemo(() => iceData?.forecast_backtest || null, [iceData]);
  const fc = useMemo(() => {
    const fcs = forecastData?.forecasts || [];
    return fcs.find((f: any) => f.forecast_hour === iceForecastHour) || null;
  }, [forecastData, iceForecastHour]);

  const fcUnavailable = !fc || fc.status !== 'AVAILABLE';

  const iceOverlay = useMemo(() => {
    if (!iceData?.overlay) return null;
    return { url: iceData.overlay.url, bounds: iceData.overlay.bounds };
  }, [iceData]);
  const riskOverlay = useMemo(() => {
    if (!riskData?.overlay) return null;
    return { url: riskData.overlay.url, bounds: riskData.overlay.bounds };
  }, [riskData]);
  const weatherOverlay = useMemo(() => {
    if (!weatherData?.overlay) return null;
    return { url: weatherData.overlay.url, bounds: weatherData.overlay.bounds };
  }, [weatherData]);
  const bathymetryOverlay = useMemo(() => {
    if (!bathyData?.overlay) return null;
    return { url: bathyData.overlay.url, bounds: bathyData.overlay.bounds };
  }, [bathyData]);

  const oceanVectors = useMemo(() => oceanData?.vectors || [], [oceanData]);
  const toggle = (k: LayerKey) => setLayers(l => ({ ...l, [k]: !l[k] }));

  const activeRoute = routes.find((r) => r.mode === activeRouteMode) || routes[0] || null;

  const downloadPdfReport = useCallback(() => {
    if (!activeRoute) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>IAVNS Voyage Report - ${vessel.name} - ${activeRoute.mode} ROUTE</title>
        <style>
          body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 30px; color: #0f172a; line-height: 1.5; }
          .header { text-align: center; border-bottom: 2px solid #0284c7; padding-bottom: 15px; margin-bottom: 20px; }
          .header h1 { margin: 0; font-size: 22px; color: #0369a1; text-transform: uppercase; letter-spacing: 1px; }
          .header p { margin: 4px 0 0 0; font-size: 11px; color: #64748b; font-weight: bold; }
          .section { margin-bottom: 20px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; background: #f8fafc; }
          .section-title { font-size: 13px; font-weight: bold; color: #0f172a; text-transform: uppercase; margin-bottom: 10px; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; }
          .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 12px; }
          .card { background: white; padding: 8px 12px; border-radius: 6px; border: 1px solid #e2e8f0; }
          .card-label { font-size: 9px; color: #64748b; text-transform: uppercase; }
          .card-val { font-size: 14px; font-weight: bold; color: #0369a1; }
          table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
          th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }
          th { background: #e2e8f0; font-weight: bold; color: #334155; }
          .footer { margin-top: 30px; font-size: 10px; color: #94a3b8; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 10px; }
          @media print { body { margin: 0; } }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>Indian Antarctica Vessels Navigation System (IAVNS)</h1>
          <p>NATIONAL CENTRE FOR POLAR AND OCEAN RESEARCH (NCPOR) · MoES · ISRO</p>
          <p style="margin-top:8px;"><strong>OFFICIAL VOYAGE & ROUTE SAFETY REPORT</strong> | Generated: ${new Date().toUTCString()}</p>
        </div>

        <div class="section">
          <div class="section-title">1. Vessel & Expedition Overview</div>
          <div class="grid">
            <div class="card"><div class="card-label">Vessel Name</div><div class="card-val">${vessel.name}</div></div>
            <div class="card"><div class="card-label">Ice Class</div><div class="card-val">${vessel.iceClass}</div></div>
            <div class="card"><div class="card-label">Max Draft</div><div class="card-val">${vessel.draft} m</div></div>
            <div class="card"><div class="card-label">Max Speed</div><div class="card-val">${vessel.maxSpeed} kn</div></div>
          </div>
        </div>

        <div class="section">
          <div class="section-title">2. Route Optimization Summary (${activeRoute.mode} MODE)</div>
          <div class="grid">
            <div class="card"><div class="card-label">Total Distance</div><div class="card-val">${activeRoute.distance_nm} NM</div></div>
            <div class="card"><div class="card-label">Estimated Time (ETA)</div><div class="card-val">${activeRoute.estimated_time_hours} Hours</div></div>
            <div class="card"><div class="card-label">Estimated Fuel</div><div class="card-val">${activeRoute.fuel_tonnes} Tonnes</div></div>
            <div class="card"><div class="card-label">Safety Rating</div><div class="card-val" style="color: ${activeRoute.safety_score > 80 ? '#16a34a' : '#d97706'}">${activeRoute.safety_score}%</div></div>
          </div>
          <p style="font-size: 11px; color: #334155; margin-top: 10px;"><strong>Assessment Notes:</strong> ${activeRoute.explanation_text || 'Optimal safe transit trajectory avoiding major sea-ice pack and iceberg threat zones.'}</p>
        </div>

        <div class="section">
          <div class="section-title">3. Explainable Risk Component Breakdown</div>
          <div class="grid" style="grid-template-columns: repeat(5, 1fr);">
            <div class="card"><div class="card-label">Sea Ice Risk</div><div class="card-val">${(activeRoute.risk_breakdown?.sea_ice || 0).toFixed(1)}</div></div>
            <div class="card"><div class="card-label">Iceberg Proximity</div><div class="card-val">${(activeRoute.risk_breakdown?.iceberg_total || 0).toFixed(1)}</div></div>
            <div class="card"><div class="card-label">ERA5 Weather</div><div class="card-val">${(activeRoute.risk_breakdown?.weather || 0).toFixed(1)}</div></div>
            <div class="card"><div class="card-label">GEBCO Depth</div><div class="card-val">${(activeRoute.risk_breakdown?.bathymetry || 0).toFixed(1)}</div></div>
            <div class="card"><div class="card-label">GLORYS Currents</div><div class="card-val">${(activeRoute.risk_breakdown?.current || 0).toFixed(1)}</div></div>
          </div>
        </div>

        <div class="section">
          <div class="section-title">4. Planned Waypoint Sequence (${activeRoute.path_points?.length || 0} Waypoints)</div>
          <table>
            <thead>
              <tr>
                <th>Waypoint #</th>
                <th>Latitude</th>
                <th>Longitude</th>
                <th>Segment Description</th>
              </tr>
            </thead>
            <tbody>
              ${(activeRoute.path_points || []).slice(0, 15).map((pt: any, idx: number) => `
                <tr>
                  <td>WP-${idx + 1}</td>
                  <td>${pt.lat.toFixed(4)}° S</td>
                  <td>${Math.abs(pt.lon).toFixed(4)}° ${pt.lon < 0 ? 'W' : 'E'}</td>
                  <td>${idx === 0 ? 'Departure (Origin)' : idx === activeRoute.path_points.length - 1 ? 'Arrival (Destination)' : 'Navigational Transit Waypoint'}</td>
                </tr>
              `).join('')}
              ${(activeRoute.path_points?.length || 0) > 15 ? `<tr><td colspan="4" style="text-align:center; color:#64748b;">... ${(activeRoute.path_points.length - 15)} additional intermediate waypoints omitted for summary brevity ...</td></tr>` : ''}
            </tbody>
          </table>
        </div>

        <div class="footer">
          <p>CONFIDENTIAL — FOR NAVIGATIONAL DECISION SUPPORT PURPOSES ONLY. ADVISORY POLAR CODE NOTICE (PS-26059).</p>
          <p>Indian Antarctica Vessels Navigation System (IAVNS) · NCPOR Antarctic Expedition Support</p>
        </div>

        <script>
          window.onload = function() { window.print(); };
        </script>
      </body>
      </html>
    `;
    printWindow.document.write(htmlContent);
    printWindow.document.close();
  }, [activeRoute, vessel]);

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-slate-950 text-slate-200 font-sans select-none">
      
      {/* ── 100% FULL-SCREEN MAP CANVAS ────────────────────────────────────────── */}
      <div className="absolute inset-0 z-0">
        <AntarcticMap
          icebergs={mapIcebergs}
          predictedTracks={predictedTracks}
          routes={routes}
          activeRouteMode={activeRouteMode}
          layers={layers}
          iceOverlay={iceOverlay}
          riskOverlay={riskOverlay}
          weatherOverlay={weatherOverlay}
          bathymetryOverlay={bathymetryOverlay}
          oceanHint={layers.currents ? oceanVectors : undefined}
          origin={origin}
          destination={dest}
          pickMode={pickMode}
          onPick={handleMapPick}
          onIcebergSelect={handleIcebergSelect}
        />
      </div>

      {/* ── TOP-LEFT FLOATING SEARCH & BRAND BAR (GOOGLE MAPS STYLE) ─────────── */}
      <div className="absolute top-3 left-3 z-30 flex items-center space-x-2 max-w-full">
        {/* Main Floating Glass Bar */}
        <div className="bg-slate-900/90 border border-slate-700/80 backdrop-blur-md px-3 py-2 rounded-2xl shadow-2xl flex items-center space-x-3">
          {/* Drawer Menu Button (☰) */}
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className={`p-2 rounded-xl transition-all ${
              isMenuOpen
                ? 'bg-sky-500 text-slate-950 shadow-lg glow-sky-sm'
                : 'bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700'
            }`}
            title="Toggle Menu Options"
          >
            {isMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          {/* Brand Logo & Name */}
          <div className="flex items-center space-x-2.5 pr-1">
            <div className="w-8 h-8 rounded-xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center">
              <Anchor className="w-4 h-4 text-sky-400" />
            </div>
            <div>
              <div className="text-sky-400 font-bold text-sm tracking-widest font-display leading-none">IAVNS</div>
              <div className="text-slate-400 text-[9px] font-mono tracking-wide uppercase">NCPOR · MoES</div>
            </div>
          </div>

          <div className="h-6 w-px bg-slate-700/80 hidden sm:block" />

          {/* Vessel Profile Badge */}
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-slate-800/60 border border-slate-700/60 text-xs font-mono">
            <span className="text-slate-200 font-bold">{vessel.name}</span>
            <span className="px-1.5 py-0.2 bg-sky-950 border border-sky-800 text-sky-400 rounded text-[10px] font-bold">{vessel.iceClass}</span>
          </div>

          <div className="h-6 w-px bg-slate-700/80 hidden md:block" />

          {/* Mode Toggle Button (LIVE API vs DEMO) */}
          <button
            onClick={() => setDemoMode(!demoMode)}
            title="Click to toggle between Live Backend API and Offline Demo Mode"
            className="cursor-pointer hover:opacity-90 transition-all transform active:scale-95"
          >
            <DataChip label="MODE" value={demoMode ? 'DEMO' : 'LIVE API'} tone={demoMode ? 'warn' : 'ok'} />
          </button>
        </div>

        {/* Pick Mode Overlay Hint Banner */}
        {pickMode && (
          <div className="bg-sky-500 text-slate-950 px-3 py-2 rounded-2xl shadow-xl text-xs font-mono font-bold flex items-center space-x-2 animate-bounce">
            <Crosshair className="w-4 h-4" />
            <span>Click map to set {pickMode === 'origin' ? 'ORIGIN' : 'DESTINATION'}</span>
          </div>
        )}
      </div>

      {/* ── SLIDE-OUT FLOATING DRAWER MENU (TOGGLE MENU) ─────────────────────────── */}
      {isMenuOpen && (
        <div className="absolute top-16 left-3 bottom-24 z-30 w-84 sm:w-96 bg-slate-900/95 border border-slate-700/80 backdrop-blur-xl rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
          
          {/* Drawer Header Tabs */}
          <div className="p-3 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
            <div className="flex space-x-1">
              {([
                ['layers', 'Layers', Layers],
                ['route', 'Route Planner', Navigation],
                ['vessel', 'Vessel', Anchor],
                ['status', 'Data & ML', Activity],
              ] as [typeof menuTab, string, any][]).map(([tabKey, label, Icon]) => (
                <button
                  key={tabKey}
                  onClick={() => setMenuTab(tabKey)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs font-mono font-semibold flex items-center space-x-1 transition-all ${
                    menuTab === tabKey
                      ? 'bg-sky-600 text-white shadow-md'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
            <button
              onClick={() => setIsMenuOpen(false)}
              className="p-1 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Content Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs">
            
            {/* TAB 1: LAYERS CHECKLIST */}
            {menuTab === 'layers' && (
              <div className="space-y-3">
                <div className="text-slate-400 font-bold uppercase tracking-wider text-[11px] flex items-center">
                  <Eye className="w-3.5 h-3.5 mr-1.5 text-sky-400" /> Map Display Layers
                </div>
                <div className="space-y-1.5 bg-slate-950/40 p-2.5 rounded-xl border border-slate-800">
                  {([
                    ['seaIce', 'Sea Ice Concentration', 'AMSR2 25 km satellite grid'],
                    ['referenceIcebergs', 'Reference Icebergs', 'BYU MERS validated tracks'],
                    ['sarCandidates', 'SAR Candidates', 'Sentinel-1 radar detections'],
                    ['predictedIcebergs', 'Predicted Icebergs', 'LSTM 1d–7d forecast trajectories'],
                    ['risk', 'Risk Heatmap', 'Dynamic composite hazard score'],
                    ['route', 'Optimized Routes', 'A* safe vessel pathfinding'],
                    ['currents', 'Ocean Currents', 'GLORYS surface vectors'],
                    ['weather', 'Weather (ERA5 Wind)', '10m wind speed heatmap'],
                    ['bathymetry', 'Bathymetry (GEBCO)', 'Seafloor depth contour'],
                  ] as [LayerKey, string, string][]).map(([key, label, desc]) => (
                    <label
                      key={key}
                      className={`flex items-start p-2 rounded-xl border transition-colors cursor-pointer ${
                        layers[key]
                          ? 'bg-sky-950/40 border-sky-800/60 text-slate-200'
                          : 'bg-slate-900/40 border-slate-800/50 text-slate-400 hover:bg-slate-800/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 mr-3 accent-sky-500 w-4 h-4"
                        checked={layers[key]}
                        onChange={() => toggle(key)}
                      />
                      <div className="flex-1">
                        <div className="font-bold text-xs flex items-center justify-between">
                          <span>{label}</span>
                          {key === 'currents' && !oceanData && <span className="text-[9px] text-yellow-500">LOADING</span>}
                        </div>
                        <div className="text-[10px] text-slate-500 font-sans">{desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 2: ROUTE PLANNER */}
            {menuTab === 'route' && (
              <div className="space-y-4">
                <div className="text-slate-400 font-bold uppercase tracking-wider text-[11px] flex items-center">
                  <SlidersHorizontal className="w-3.5 h-3.5 mr-1.5 text-sky-400" /> Route Optimizer Settings
                </div>

                {/* Mode Selector */}
                <div className="grid grid-cols-4 gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
                  {(['FASTEST', 'SAFEST', 'BALANCED', 'CUSTOM'] as RouteMode[]).map((m) => (
                    <button
                      key={m}
                      onClick={() => setRouteMode(m)}
                      className={`py-1.5 rounded-lg text-[10px] font-bold transition-all ${
                        routeMode === m
                          ? 'bg-sky-600 text-white shadow'
                          : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>

                {/* Custom Weight Sliders (if CUSTOM) */}
                {routeMode === 'CUSTOM' && (
                  <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800 space-y-2">
                    <div className="text-[10px] text-sky-400 font-bold uppercase">Custom Optimization Weights</div>
                    {[
                      ['distance', 'Distance', 0.1, 2.0],
                      ['safety', 'Safety', 0.1, 2.0],
                      ['fuel', 'Fuel', 0.1, 2.0],
                      ['current', 'Current', 0.1, 2.0],
                    ].map(([key, label, min, max]) => (
                      <div key={key} className="space-y-1">
                        <div className="flex justify-between text-[10px]">
                          <span>{label}</span>
                          <span className="text-sky-400">{(customWeights as any)[key].toFixed(1)}</span>
                        </div>
                        <input
                          type="range"
                          min={min}
                          max={max}
                          step={0.1}
                          value={(customWeights as any)[key]}
                          onChange={(e) => setCustomWeights({ ...customWeights, [key]: Number(e.target.value) })}
                          className="w-full accent-sky-500 h-1 bg-slate-800 rounded"
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* Origin / Dest Input Fields */}
                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-[10px] text-slate-400 font-bold uppercase">Coordinates Selection</div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setPickMode(pickMode === 'origin' ? null : 'origin')}
                      className={`flex items-center justify-center py-1.5 rounded-lg text-[10px] font-bold border transition-colors ${
                        pickMode === 'origin' ? 'bg-green-600 text-white border-green-500' : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <MapPin className="w-3 h-3 mr-1" /> Pick Origin
                    </button>
                    <button
                      onClick={() => setPickMode(pickMode === 'destination' ? null : 'destination')}
                      className={`flex items-center justify-center py-1.5 rounded-lg text-[10px] font-bold border transition-colors ${
                        pickMode === 'destination' ? 'bg-amber-600 text-white border-amber-500' : 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <Crosshair className="w-3 h-3 mr-1" /> Pick Dest
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <label className="text-slate-400">Origin Lat/Lon
                      <input className="w-full bg-slate-900 border border-slate-700 px-2 py-1 text-slate-200 mt-1 rounded-lg" type="number" step="0.5"
                        value={origin.lat} onChange={e => setOrigin({ ...origin, lat: Number(e.target.value) })} />
                    </label>
                    <label className="text-slate-400">Dest Lat/Lon
                      <input className="w-full bg-slate-900 border border-slate-700 px-2 py-1 text-slate-200 mt-1 rounded-lg" type="number" step="0.5"
                        value={dest.lat} onChange={e => setDest({ ...dest, lat: Number(e.target.value) })} />
                    </label>
                  </div>
                  <button
                    onClick={() => { setOrigin({ lat: -63.5, lon: -60.0 }); setDest({ lat: -68.0, lon: -40.0 }); }}
                    className="w-full py-1.5 bg-sky-950/60 hover:bg-sky-900 border border-sky-800 text-sky-400 rounded-lg text-[10px] font-bold transition-colors"
                  >
                    ⚓ Reset Antarctic Sea Points (-63.5°S, -68.0°S)
                  </button>
                </div>

                <button
                  onClick={computeRoute}
                  disabled={routing}
                  className="w-full py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold tracking-wider uppercase text-xs shadow-lg transition-all"
                >
                  {routing ? '⚙ Computing Route...' : `▶ Compute ${routeMode} Route`}
                </button>
              </div>
            )}

            {/* TAB 3: VESSEL CONFIGURATION */}
            {menuTab === 'vessel' && (
              <div className="space-y-4">
                <div className="text-slate-400 font-bold uppercase tracking-wider text-[11px] flex items-center">
                  <Anchor className="w-3.5 h-3.5 mr-1.5 text-sky-400" /> Vessel Specs (NCPOR R/V Bharathi)
                </div>

                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800 space-y-3">
                  <div>
                    <label className="text-slate-400 text-[10px] uppercase">Vessel Name</label>
                    <input className="w-full bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-slate-200 mt-1 rounded-lg text-xs" type="text"
                      value={vessel.name} onChange={e => setVessel({ ...vessel, name: e.target.value })} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-400 text-[10px] uppercase">Ice Class</label>
                      <select className="w-full bg-slate-900 border border-slate-700 px-2 py-1.5 text-slate-200 mt-1 rounded-lg text-xs"
                        value={vessel.iceClass} onChange={e => setVessel({ ...vessel, iceClass: e.target.value })}>
                        {['PC1', 'PC2', 'PC3', 'PC4', 'PC5', 'PC6', 'PC7', 'IA_SUPER', 'IA', 'IB', 'IC'].map(c => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-slate-400 text-[10px] uppercase">Draft (meters)</label>
                      <input className="w-full bg-slate-900 border border-slate-700 px-2 py-1.5 text-slate-200 mt-1 rounded-lg text-xs" type="number" step="0.1"
                        value={vessel.draft} onChange={e => setVessel({ ...vessel, draft: Number(e.target.value) })} />
                    </div>
                  </div>
                  <div>
                    <label className="text-slate-400 text-[10px] uppercase">Max Speed (knots)</label>
                    <input className="w-full bg-slate-900 border border-slate-700 px-2 py-1.5 text-slate-200 mt-1 rounded-lg text-xs" type="number" step="0.5"
                      value={vessel.maxSpeed} onChange={e => setVessel({ ...vessel, maxSpeed: Number(e.target.value) })} />
                  </div>
                  <div className="space-y-2 pt-1 border-t border-slate-800">
                    <label className="flex items-center space-x-2 text-xs cursor-pointer">
                      <input type="checkbox" className="accent-sky-500 w-4 h-4" checked={vessel.icebreakingCapable}
                        onChange={e => setVessel(v => ({ ...v, icebreakingCapable: e.target.checked }))} />
                      <span>Icebreaking Capable</span>
                    </label>
                    <label className="flex items-center space-x-2 text-xs cursor-pointer">
                      <input type="checkbox" className="accent-sky-500 w-4 h-4" checked={vessel.dedicatedIcebreaker}
                        onChange={e => setVessel(v => ({ ...v, dedicatedIcebreaker: e.target.checked, icebreakingCapable: e.target.checked || v.icebreakingCapable }))} />
                      <span>Dedicated Polar Icebreaker</span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: DATASETS & ML STATUS */}
            {menuTab === 'status' && (
              <div className="space-y-4">
                <div className="text-slate-400 font-bold uppercase tracking-wider text-[11px] flex items-center">
                  <Activity className="w-3.5 h-3.5 mr-1.5 text-sky-400" /> Data Ingestion & ML Pipeline
                </div>

                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-[10px] text-slate-400 font-bold uppercase">Ingested Datasets</div>
                  {datasets.map((d: any) => (
                    <div key={d.name} className="flex items-center justify-between text-xs py-1 border-b border-slate-800/50">
                      <span className="font-bold text-slate-300">{d.name}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] ${d.files_found > 0 ? 'bg-green-950 text-green-400 border border-green-800' : 'bg-red-950 text-red-400'}`}>
                        {d.status} ({d.files_found} files)
                      </span>
                    </div>
                  ))}
                </div>

                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-[10px] text-slate-400 font-bold uppercase">ML Models & Metrics</div>
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between">
                      <span>LSTM Iceberg Model:</span>
                      <span className="text-sky-400 font-bold">{mlStatus?.iceberg_trajectory?.model_status || 'LSTM'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Sea-Ice Optical Flow:</span>
                      <span className="text-sky-400 font-bold">{mlStatus?.sea_ice_nowcast?.model_status || 'OPTICAL_FLOW'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>SAR Candidate Detector:</span>
                      <span className="text-yellow-500 font-bold">Sentinel-1 CFAR</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── FLOATING ROUTE NAVIGATION CARD (GOOGLE MAPS STYLE BOTTOM PANEL) ─────── */}
      {activeRoute && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 w-11/12 max-w-2xl bg-slate-900/90 border border-slate-700/80 backdrop-blur-md p-3.5 rounded-2xl shadow-2xl flex flex-col space-y-2 animate-slide-up">
          
          {/* Card Top Row: Route Mode & Primary Metrics */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className={`px-2.5 py-1 rounded-xl text-xs font-bold font-mono tracking-wider shadow ${
                activeRoute.mode === 'SAFEST' ? 'bg-emerald-600 text-white' :
                activeRoute.mode === 'FASTEST' ? 'bg-amber-600 text-white' :
                'bg-sky-600 text-white'
              }`}>
                {activeRoute.mode} ROUTE
              </span>
              {activeRoute.fallback && (
                <span className="px-2 py-0.5 bg-amber-950 text-amber-400 border border-amber-800 text-[10px] font-mono rounded-lg">
                  ⚠ FALLBACK PATH
                </span>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center space-x-1.5">
              <button
                onClick={downloadPdfReport}
                className="px-2.5 py-1 bg-sky-950/80 hover:bg-sky-900 text-sky-400 rounded-xl text-xs font-mono font-bold flex items-center space-x-1 border border-sky-800 transition-colors"
                title="Download Official Voyage PDF Report"
              >
                <span>📥 PDF Report</span>
              </button>
              <button
                onClick={() => setShowRiskDetails(!showRiskDetails)}
                className="px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-mono flex items-center space-x-1 border border-slate-700"
              >
                <Gauge className="w-3.5 h-3.5 text-sky-400" />
                <span>Explainable Risk</span>
                {showRiskDetails ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Metrics Grid Bar */}
          <div className="grid grid-cols-4 gap-2 font-mono text-center bg-slate-950/50 p-2 rounded-xl border border-slate-800/80">
            <div>
              <div className="text-slate-500 text-[9px] uppercase">Distance</div>
              <div className="text-sky-400 font-bold text-sm">{activeRoute.distance_nm} <span className="text-[10px] text-slate-400 font-normal">NM</span></div>
            </div>
            <div>
              <div className="text-slate-500 text-[9px] uppercase">ETA</div>
              <div className="text-slate-200 font-bold text-sm">{activeRoute.estimated_time_hours} <span className="text-[10px] text-slate-400 font-normal">h</span></div>
            </div>
            <div>
              <div className="text-slate-500 text-[9px] uppercase">Fuel</div>
              <div className="text-slate-200 font-bold text-sm">{activeRoute.fuel_tonnes} <span className="text-[10px] text-slate-400 font-normal">t</span></div>
            </div>
            <div>
              <div className="text-slate-500 text-[9px] uppercase">Safety Score</div>
              <div className={`font-bold text-sm ${activeRoute.safety_score > 80 ? 'text-green-400' : 'text-yellow-400'}`}>
                {activeRoute.safety_score}%
              </div>
            </div>
          </div>

          {/* Hazard Summary Text */}
          {activeRoute.explanation_text && (
            <div className="text-[10px] font-sans text-slate-300 leading-tight">
              {activeRoute.explanation_text}
            </div>
          )}

          {/* Expandable Risk Breakdown Popup Details */}
          {showRiskDetails && activeRoute.risk_breakdown && (
            <div className="pt-2 border-t border-slate-800 space-y-2 animate-fade-in font-mono text-xs">
              <div className="text-[10px] text-sky-400 font-bold uppercase flex items-center justify-between">
                <span>Per-Component Risk Breakdown</span>
                <span className="text-slate-400">{activeRoute.primary_hazard}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {RISK_COMPONENTS.map(({ key, label }) => {
                  const val = activeRoute.risk_breakdown[key] || 0;
                  return (
                    <div key={key} className="bg-slate-950 p-2 rounded-xl border border-slate-800/80">
                      <div className="text-slate-500 text-[9px] uppercase">{label}</div>
                      <div className="text-xs font-bold text-slate-200 mt-0.5">{val.toFixed(1)}</div>
                      <div className="w-full bg-slate-800 h-1 rounded-full mt-1.5 overflow-hidden">
                        <div className="bg-sky-400 h-full rounded-full" style={{ width: `${Math.min(100, val * 2)}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── FLOATING BOTTOM-RIGHT CONTROLS ────────────────────────────────────── */}
      <div className="absolute bottom-4 right-3 z-30 flex flex-col items-end space-y-2">
        {/* Forecast Horizon Selector Pill */}
        <div className="bg-slate-900/90 border border-slate-700/80 backdrop-blur-md p-1.5 rounded-xl shadow-xl flex items-center space-x-1 font-mono text-[10px]">
          <span className="text-slate-400 px-1 font-bold">Horizon:</span>
          {FORECAST_HORIZONS.map((h) => (
            <button
              key={h}
              onClick={() => setForecastHorizon(h)}
              className={`px-2 py-0.5 rounded-lg font-bold transition-all ${
                forecastHorizon === h
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:bg-slate-800'
              }`}
            >
              {h}h
            </button>
          ))}
        </div>
      </div>

    </div>
  );
}

export default App;
