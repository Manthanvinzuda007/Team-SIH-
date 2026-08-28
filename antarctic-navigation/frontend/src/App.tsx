import { useMemo, useState, useEffect, useCallback } from 'react';
import { Activity, Anchor, Navigation, Thermometer, Layers, AlertTriangle, Wifi, WifiOff } from 'lucide-react';

import AntarcticMap, { LayerKey } from './components/Map';
import { usePollingApi } from './hooks/useApi';

function App() {
  // Live UTC clock
  const [currentTime, setCurrentTime] = useState(new Date().toISOString());
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date().toISOString()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Map layers
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    ice: true, icebergs: true, risk: true, route: true, currents: false,
  });

  // Route planner
  const [origin, setOrigin] = useState({ lat: -63.5, lon: -60.0 });
  const [dest, setDest] = useState({ lat: -68.0, lon: -40.0 });
  const [forecastHour, setForecastHour] = useState(24);

  // Vessel configuration — PC1 is NOT automatically an icebreaker
  const [vessel, setVessel] = useState({
    iceClass: 'PC3',
    draft: 8.0,
    maxSpeed: 12.0,
    icebreakingCapable: false,
    dedicatedIcebreaker: false,
  });

  // API data hooks
  const { data: icebergsRaw, isLoading: icebergsLoading, error: icebergsError } = usePollingApi<any>('/icebergs?limit=500', 60000);
  const { data: statusData } = usePollingApi<any>('/data-status', 60000);
  const { data: riskData } = usePollingApi<any>('/risk-map', 120000);
  const { data: iceData } = usePollingApi<any>('/sea-ice/current', 120000);
  const { data: forecastData } = usePollingApi<any>(`/sea-ice/forecast?hours=${[6,12,18,24,30,36,42,48].join(',')}`, 120000);
  const { data: oceanData } = usePollingApi<any>('/ocean?subsample=10', 120000);
  const { error: healthError } = usePollingApi<any>('/health', 30000);

  const isOffline = !!(healthError);
  const isPipelineReady = !!(iceData || riskData);

  // Route state
  const [routes, setRoutes] = useState<any[]>([]);
  const [routing, setRouting] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  const computeRoute = useCallback(async () => {
    setRouting(true);
    setRouteError(null);
    try {
      const res = await fetch('/api/routes/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
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
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ message: `HTTP ${res.status}` }));
        throw new Error(err.message || err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRoutes(data.routes || []);
    } catch (e: any) {
      setRouteError(e.message || 'Route computation failed');
      setRoutes([]);
    } finally {
      setRouting(false);
    }
  }, [origin, dest, vessel]);

  // Extract icebergs from wrapped response
  const icebergs = icebergsRaw?.icebergs || icebergsRaw || [];
  const mapIcebergs = Array.isArray(icebergs) ? icebergs.filter((i: any) =>
    i.source === 'S1_CFAR' || (i.lat <= -60 && i.lat >= -75 && i.lon >= -80 && i.lon <= -10)
  ) : [];

  const datasets = statusData?.datasets || [];

  // Forecast for selected horizon
  const allForecasts = forecastData?.forecasts || [];
  const fc = allForecasts.find((f: any) => f.forecast_hour === forecastHour);
  const fcUnavailable = fc?.status === 'UNAVAILABLE';
  const backtest = iceData?.forecast_backtest || forecastData?.backtest;

  // Image overlays
  const iceOverlay = useMemo(() => {
    if (!iceData?.overlay) return null;
    return { url: iceData.overlay.url, bounds: iceData.overlay.bounds };
  }, [iceData]);
  const riskOverlay = useMemo(() => {
    if (!riskData?.overlay) return null;
    return { url: riskData.overlay.url, bounds: riskData.overlay.bounds };
  }, [riskData]);

  // Ocean current vectors for map
  const oceanVectors = useMemo(() => oceanData?.vectors || [], [oceanData]);

  const toggle = (k: LayerKey) => setLayers(l => ({ ...l, [k]: !l[k] }));

  return (
    <div className="flex flex-col h-screen bg-polaris-dark text-polaris-text_bright font-sans">
      {/* ── Header ────────────────────────────────────────────────── */}
      <header className="h-12 border-b border-polaris-border bg-polaris-panel flex items-center justify-between px-4 select-none">
        <div className="flex items-center space-x-4">
          <div className="flex items-center text-polaris-accent font-bold tracking-widest text-lg">
            <Anchor className="w-5 h-5 mr-2" />
            POLARIS <span className="text-polaris-text ml-2 text-sm font-normal">ANTARCTIC NAVIGATION</span>
          </div>
        </div>
        <div className="flex items-center space-x-6 text-sm font-mono text-polaris-text">
          <div className="flex items-center space-x-2">
            <span className="text-polaris-text_bright">R/V POLARIS</span>
            <span className="px-1.5 py-0.5 bg-polaris-border rounded text-xs text-polaris-accent">{vessel.iceClass}</span>
            {vessel.dedicatedIcebreaker && <span className="px-1.5 py-0.5 bg-blue-900 rounded text-xs text-blue-300">ICEBREAKER</span>}
          </div>
          <div>UTC {currentTime.substring(11, 19)}</div>
          <div className="flex items-center space-x-1">
            {isOffline
              ? <><WifiOff className="w-4 h-4 text-red-400" /><span className="text-red-400">OFFLINE</span></>
              : <><Wifi className="w-4 h-4 text-green-400" /><span className="text-green-400">ONLINE</span></>
            }
          </div>
          <div className="flex items-center text-polaris-success">
            <Activity className="w-4 h-4 mr-1" />
            ADVISORY ONLY
          </div>
        </div>
      </header>

      {/* ── Offline banner ──────────────────────────────────────── */}
      {isOffline && (
        <div className="bg-red-900/80 text-red-100 px-4 py-2 text-xs font-mono font-bold flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 mr-2" />
          BACKEND OFFLINE — Unable to connect to navigation API. Auto-reconnecting every 30s…
        </div>
      )}

      {/* ── Main content ─────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar — layers + data status */}
        <aside className="w-64 border-r border-polaris-border bg-polaris-panel flex flex-col">
          <div className="p-3 border-b border-polaris-border font-semibold text-xs tracking-wider text-polaris-text uppercase flex items-center">
            <Layers className="w-4 h-4 mr-2" />
            Active Layers
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {([
              ['ice', 'Sea Ice Concentration'],
              ['icebergs', 'Icebergs (BYU + SAR CFAR)'],
              ['risk', 'Risk Heatmap'],
              ['route', 'Optimized Routes'],
              ['currents', 'Ocean Currents (GLORYS)'],
            ] as [LayerKey, string][]).map(([key, label]) => (
              <label key={key} className="flex items-center p-2 rounded hover:bg-polaris-border cursor-pointer text-sm">
                <input type="checkbox" className="mr-3 accent-polaris-accent" checked={layers[key]} onChange={() => toggle(key)} />
                {label}
                {key === 'currents' && !oceanData && <span className="ml-auto text-[9px] text-yellow-500">LOADING</span>}
              </label>
            ))}
            <p className="text-[10px] text-polaris-text px-2 pt-2">
              Map is Web Mercator. Analysis/routing grid is EPSG:3031 at 10 km. Static Aug 2026 files — not a live feed.
            </p>
          </div>

          {/* Data Status Panel */}
          <div className="p-3 border-t border-polaris-border max-h-52 overflow-y-auto">
            <div className="font-semibold text-xs tracking-wider text-polaris-text uppercase flex items-center mb-2">
              <AlertTriangle className="w-3 h-3 mr-1" />
              Data Status
            </div>
            <div className="text-[10px] text-polaris-text space-y-1 font-mono">
              {datasets.length === 0 && !isOffline && <div>Loading datasets…</div>}
              {datasets.length === 0 && isOffline && <div className="text-red-400">Cannot load data status</div>}
              {datasets.map((d: any) => (
                <div key={d.name} className="flex items-start space-x-1">
                  <span className={d.files_found > 0 ? 'text-green-400' : 'text-red-400'}>●</span>
                  <div>
                    <div className="font-bold">{d.name}</div>
                    <div>{d.status} · {d.files_found} files</div>
                    {d.data_age_hours != null && <div className="text-yellow-600">{d.data_age_hours.toFixed(0)}h mtime age</div>}
                  </div>
                </div>
              ))}
              {statusData?.demo_window && (
                <div className="mt-2 pt-1 border-t border-polaris-border/30 text-yellow-600">
                  {statusData.demo_window}
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Map */}
        <main className="flex-1 relative bg-slate-900 border-r border-polaris-border">
           <AntarcticMap
             icebergs={mapIcebergs}
             routes={routes}
             layers={layers}
             iceOverlay={iceOverlay}
             riskOverlay={riskOverlay}
             oceanHint={layers.currents ? oceanVectors : undefined}
           />
        </main>

        {/* Right sidebar — route comparison + icebergs */}
        <aside className="w-80 bg-polaris-panel flex flex-col">
          {/* Route Comparison */}
          <div className="h-1/2 border-b border-polaris-border flex flex-col">
            <div className="p-3 border-b border-polaris-border font-semibold text-xs tracking-wider text-polaris-text uppercase flex items-center justify-between">
              <div className="flex items-center"><Navigation className="w-4 h-4 mr-2" /> Route Comparison</div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {routeError && (
                <div className="text-xs font-mono text-red-400 border border-red-800 rounded p-2 bg-red-950">
                  ⚠ {routeError}
                </div>
              )}
              {routes.length === 0 && !routeError ? (
                <div className="text-xs font-mono text-polaris-text">No routes yet. Set origin/dest and compute.</div>
              ) : (
                routes.map(r => (
                  <div key={r.mode} className={`text-xs font-mono border rounded p-2 bg-polaris-dark ${r.fallback ? 'border-yellow-700' : 'border-polaris-border'}`}>
                    <div className="flex justify-between font-bold mb-1">
                      <span className={r.mode === 'FASTEST' ? 'text-yellow-400' : r.mode === 'SAFEST' ? 'text-green-400' : 'text-white'}>{r.mode}</span>
                      <span>{r.distance_nm} NM</span>
                    </div>
                    {r.fallback && (
                      <div className="text-yellow-500 text-[10px] mb-1">⚠ FALLBACK: {r.fallback_reason}</div>
                    )}
                    <div className="text-polaris-text mb-0.5">
                      ETA: {r.estimated_time_hours}h @ {r.effective_speed_knots ?? r.base_speed_knots} kn
                    </div>
                    <div className="text-polaris-text mb-0.5">
                      Fuel: {r.fuel_tonnes}t <span className="text-[9px] text-polaris-text/60">({r.fuel_model || 'proxy'})</span>
                    </div>
                    <div className="text-polaris-text mb-1">
                      Risk: {r.risk_score != null ? r.risk_score.toFixed(1) + '/100' : 'N/A'} ·
                      Safety: {r.safety_score != null ? r.safety_score.toFixed(1) + '/100' : 'N/A'}
                    </div>
                    {r.ice_encounters > 0 && (
                      <div className="text-blue-300 text-[10px] mb-1">Ice encounters: {r.ice_encounters} cells &gt;15%</div>
                    )}
                    <div className="text-[10px] text-polaris-text leading-tight">{r.explanation_text}</div>
                    <div className="text-[9px] text-polaris-text/50 mt-1">Data: {r.data_valid_time}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Iceberg Table */}
          <div className="h-1/2 flex flex-col">
            <div className="p-3 border-b border-polaris-border font-semibold text-xs tracking-wider text-polaris-text uppercase flex items-center justify-between">
              <div className="flex items-center"><Thermometer className="w-4 h-4 mr-2" /> Icebergs</div>
              <span className="text-polaris-accent text-[10px]">
                {icebergsError ? 'ERROR' : `${icebergs.length} IN DB`}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto">
               {icebergsLoading ? (
                 <div className="p-2 text-xs font-mono text-polaris-text">Loading…</div>
               ) : icebergsError ? (
                 <div className="p-2 text-xs font-mono text-red-400">Failed to load icebergs</div>
               ) : icebergs.length === 0 ? (
                 <div className="p-2 text-xs font-mono text-polaris-text">No icebergs in database. Run populate_db.py first.</div>
               ) : (
                 <table className="w-full text-xs font-mono text-left">
                   <thead className="bg-polaris-border/50 text-polaris-text sticky top-0">
                     <tr>
                       <th className="px-2 py-1 font-normal">ID</th>
                       <th className="px-2 py-1 font-normal">SRC</th>
                       <th className="px-2 py-1 font-normal">CONF</th>
                     </tr>
                   </thead>
                   <tbody>
                     {icebergs.slice(0, 80).map((i: any) => (
                       <tr key={i.id} className="border-b border-polaris-border/30">
                         <td className="px-2 py-1.5 text-polaris-accent">{i.name}</td>
                         <td className="px-2 py-1.5">{i.source}</td>
                         <td className="px-2 py-1.5">{((i.confidence || 0) * 100).toFixed(0)}%</td>
                       </tr>
                     ))}
                   </tbody>
                 </table>
               )}
            </div>
          </div>
        </aside>
      </div>

      {/* ── Footer — nowcast, provenance, risk, route planner ───── */}
      <footer className="h-52 border-t border-polaris-border bg-polaris-panel flex">
        {/* Sea-ice nowcast */}
        <div className="w-1/4 border-r border-polaris-border p-3 flex flex-col">
          <div className="font-semibold text-xs tracking-wider text-polaris-text uppercase mb-2">Sea-Ice Nowcast</div>
          <div className="text-[10px] font-mono text-polaris-text mb-2">
            {backtest?.persistence_mae_fraction != null
              ? `Measured next-day MAE (fraction): persistence ${backtest.persistence_mae_fraction.toFixed(4)}, advection ${backtest.advection_mae_fraction?.toFixed(4) ?? 'n/a'} (${backtest.persistence_mae_pairs} / ${backtest.advection_mae_pairs} pairs). Not a ConvLSTM.`
              : 'Backtest loads with /sea-ice/current (8 AMSR2 days).'}
          </div>
          <input type="range" min={6} max={48} step={6} value={forecastHour}
                 onChange={e => setForecastHour(Number(e.target.value))}
                 className="w-full accent-polaris-accent" />
          <div className="text-xs font-mono mt-1">
            Horizon +{forecastHour}h ·
            {fcUnavailable
              ? <span className="text-red-400 ml-1">UNAVAILABLE ({fc?.reason || 'insufficient data'})</span>
              : <> model {fc?.model_type || '—'} · conf {fc?.confidence != null ? fc.confidence.toFixed(2) : '—'}</>
            }
          </div>
          {fc?.status === 'AVAILABLE' && fc?.mean_concentration_fraction != null && (
            <div className="text-[10px] font-mono text-polaris-text mt-1">
              Mean conc: {(fc.mean_concentration_fraction * 100).toFixed(1)}%
            </div>
          )}
        </div>

        {/* Provenance */}
        <div className="w-1/4 border-r border-polaris-border p-3 flex flex-col">
          <div className="font-semibold text-xs tracking-wider text-polaris-text uppercase mb-2">Provenance</div>
          <div className="text-[10px] font-mono text-polaris-text leading-relaxed space-y-0.5">
            <div>Ice: AMSR2 2026-08-01..08</div>
            <div>Ocean: GLORYS Jun 2026 <span className="text-yellow-500">(NOT contemporaneous)</span></div>
            <div>Weather: ERA5 Aug 1–8</div>
            <div>SAR: 1 IW HH scene 2026-08-22</div>
            <div>BYU: multi-decade tracks (625 usable)</div>
          </div>
          {oceanData?.temporal_warning && (
            <div className="text-[9px] text-yellow-600 mt-1 border-t border-polaris-border/30 pt-1">
              ⚠ {oceanData.temporal_warning}
            </div>
          )}
        </div>

        {/* Risk weights + vessel config */}
        <div className="w-1/4 border-r border-polaris-border p-3 flex flex-col">
          <div className="font-semibold text-xs tracking-wider text-polaris-text uppercase mb-2">Vessel Config</div>
          <div className="grid grid-cols-2 gap-1 text-[10px] font-mono mb-2">
            <label>Class
              <select className="w-full bg-polaris-dark border border-polaris-border px-1 text-polaris-text_bright"
                      value={vessel.iceClass} onChange={e => setVessel(v => ({ ...v, iceClass: e.target.value }))}>
                {['PC1','PC2','PC3','PC4','PC5','PC6','PC7','IA','IB','IC'].map(c =>
                  <option key={c} value={c}>{c}</option>
                )}
              </select>
            </label>
            <label>Draft(m)
              <input className="w-full bg-polaris-dark border border-polaris-border px-1" type="number" step="0.5"
                     value={vessel.draft} onChange={e => setVessel(v => ({ ...v, draft: Number(e.target.value) }))} />
            </label>
            <label>Speed(kn)
              <input className="w-full bg-polaris-dark border border-polaris-border px-1" type="number" step="1"
                     value={vessel.maxSpeed} onChange={e => setVessel(v => ({ ...v, maxSpeed: Number(e.target.value) }))} />
            </label>
            <label className="flex items-center space-x-1 col-span-2 mt-1">
              <input type="checkbox" className="accent-polaris-accent"
                     checked={vessel.dedicatedIcebreaker}
                     onChange={e => setVessel(v => ({ ...v, dedicatedIcebreaker: e.target.checked, icebreakingCapable: e.target.checked || v.icebreakingCapable }))} />
              <span>Dedicated Icebreaker</span>
            </label>
          </div>
          <div className="text-[9px] font-mono text-polaris-text/60">
            Risk: ICE {(riskData?.provenance?.weights?.ice * 100 || 35).toFixed(0)}% ·
            BERG {(riskData?.provenance?.weights?.iceberg * 100 || 30).toFixed(0)}% ·
            WX {(riskData?.provenance?.weights?.weather * 100 || 20).toFixed(0)}% ·
            BATHY {(riskData?.provenance?.weights?.bathymetry * 100 || 15).toFixed(0)}%
          </div>
        </div>

        {/* Route planner */}
        <div className="w-1/4 p-3 flex flex-col relative">
          <div className="absolute top-2 right-2 px-1.5 py-0.5 bg-polaris-accent text-polaris-dark text-[10px] font-bold rounded">HISTORICAL DEMO</div>
          <div className="font-semibold text-xs tracking-wider text-polaris-text uppercase mb-2">Route Planner</div>
          <div className="grid grid-cols-2 gap-1 text-[10px] font-mono mb-2">
            <label>O lat<input className="w-full bg-polaris-dark border border-polaris-border px-1" type="number" step="0.5"
                               value={origin.lat} onChange={e => setOrigin({ ...origin, lat: Number(e.target.value) })} /></label>
            <label>O lon<input className="w-full bg-polaris-dark border border-polaris-border px-1" type="number" step="0.5"
                               value={origin.lon} onChange={e => setOrigin({ ...origin, lon: Number(e.target.value) })} /></label>
            <label>D lat<input className="w-full bg-polaris-dark border border-polaris-border px-1" type="number" step="0.5"
                               value={dest.lat} onChange={e => setDest({ ...dest, lat: Number(e.target.value) })} /></label>
            <label>D lon<input className="w-full bg-polaris-dark border border-polaris-border px-1" type="number" step="0.5"
                               value={dest.lon} onChange={e => setDest({ ...dest, lon: Number(e.target.value) })} /></label>
          </div>
          <button onClick={computeRoute} disabled={routing || isOffline}
                  className={`w-full py-1.5 rounded text-sm font-semibold uppercase tracking-wider
                    ${isOffline ? 'bg-red-900 text-red-300 cursor-not-allowed' : 'bg-polaris-border hover:bg-polaris-accent hover:text-polaris-dark'}`}>
            {routing ? 'Computing…' : isOffline ? 'API OFFLINE' : 'Compute Routes'}
          </button>
          {!isOffline && !isPipelineReady && (
            <div className="text-[9px] text-yellow-500 mt-1 text-center">Pipeline loading… first request may take ~60s</div>
          )}
        </div>
      </footer>
    </div>
  );
}

export default App;
