import { memo, useState, useCallback, useMemo } from 'react'
import { MiniMap } from '../MiniMap/MiniMap'
import styles from './BottomPanel.module.css'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ForecastFrame {
  id: string // matches MiniMap's frameId: 'current' | '6h' | '12h' | '24h'
  label: string
  issuedAt: string
  available: boolean
}

export interface MissionOverviewData {
  seaIceConcPct: number | null
  nearestIcebergNm: number | null
  nearestIcebergBearingDeg: number | null
  compositeRisk: number | null
  iceConcChangePctPer6h: number | null
  asOfUtc: string
}

export interface RiskDashboardData {
  compositeRisk: number | null
  iceConcentrationPct: number | null
  icebergProximityPct: number | null
  weatherPct: number | null
}

export interface RoutePlannerData {
  vesselProfiles: string[]
  iceClass: string
  draftM: number
  routeComputedAt: string | null
}

export interface BottomPanelProps {
  selectedForecastId: string
  onForecastFrameSelect: (frame: ForecastFrame) => void
  routePlanner: RoutePlannerData
  onComputeRoute: (origin: string, destination: string, weighting: number) => void
  forecastFrames?: ForecastFrame[]
  missionOverview?: MissionOverviewData
  riskDashboard?: RiskDashboardData
  vesselLon?: number
  vesselLat?: number
}

// ─── Mock Data (backend-ready — every unresolved value is `null`, not a
// guessed number, so "—" on screen means "not computed yet", not "zero") ───────

export const MOCK_FORECAST_FRAMES: ForecastFrame[] = [
  { id: 'current', label: 'CURRENT', issuedAt: '14 JUL 06:00Z', available: true },
  { id: '6h', label: '+6H', issuedAt: '14 JUL 06:00Z', available: true },
  { id: '12h', label: '+12H', issuedAt: '14 JUL 06:00Z', available: true },
  { id: '24h', label: '+24H', issuedAt: '14 JUL 06:00Z', available: false },
]

// GET /api/sea-ice/current, GET /api/icebergs, GET /api/risk-assessment
export const MOCK_MISSION_OVERVIEW: MissionOverviewData = {
  seaIceConcPct: null,
  nearestIcebergNm: null,
  nearestIcebergBearingDeg: null,
  compositeRisk: null,
  iceConcChangePctPer6h: null,
  asOfUtc: '14 JUL 2026 06:00Z',
}

// GET /api/risk-assessment
export const MOCK_RISK_DASHBOARD: RiskDashboardData = {
  compositeRisk: null,
  iceConcentrationPct: null,
  icebergProximityPct: null,
  weatherPct: null,
}

export const MOCK_ROUTE_PLANNER: RoutePlannerData = {
  vesselProfiles: ['RV Aurora — PC6', 'Icebreaker — PC3', 'Cargo — PC7'],
  iceClass: 'PC6',
  draftM: 8.2,
  routeComputedAt: null,
}

const fmt = (value: number | null, suffix = '') => (value === null ? '—' : `${value}${suffix}`)

// ─── Sub: Sea-Ice Forecast ──────────────────────────────────────────────────
interface ForecastSectionProps {
  frames: ForecastFrame[]
  selectedId: string
  onSelect: (frame: ForecastFrame) => void
  vesselLon?: number
  vesselLat?: number
}

const ForecastSection = memo(({ frames, selectedId, onSelect, vesselLon, vesselLat }: ForecastSectionProps) => {
  const cells = useMemo(
    () =>
      frames.map((frame) => (
        <button
          key={frame.id}
          type="button"
          className={`${styles.forecastCell} ${frame.id === selectedId ? styles.forecastCellActive : ''}`}
          onClick={() => onSelect(frame)}
        >
          <div className={styles.forecastThumb}>
            <MiniMap
              frameId={frame.id}
              label={frame.label}
              available={frame.available}
              vesselLon={vesselLon}
              vesselLat={vesselLat}
            />
          </div>
          <span className={styles.forecastLabel}>{frame.label}</span>
          {frame.available ? (
            <span className={styles.forecastIssued}>
              ISSUED:
              <br />
              {frame.issuedAt}
            </span>
          ) : (
            <span className={styles.forecastIssued} style={{ color: '#c9453b' }}>
              UNAVAILABLE
            </span>
          )}
        </button>
      )),
    [frames, selectedId, onSelect, vesselLon, vesselLat]
  )

  return (
    <div className={`${styles.section} ${styles.sectionWide}`}>
      <div className={styles.sectionTitle}>
        SEA-ICE FORECAST <span className={styles.sectionSub}>(Concentration %)</span>
      </div>
      <div className={styles.forecastGrid}>{cells}</div>
      <div className={styles.uncertaintyRow}>
        <span>MODEL UNCERTAINTY (RMSE %)</span>
        <span>± —%</span>
        <span>± —%</span>
      </div>
    </div>
  )
})

// ─── Sub: Mission Overview ──────────────────────────────────────────────────
const MissionOverviewSection = memo(({ data }: { data: MissionOverviewData }) => (
  <div className={styles.section}>
    <div className={styles.sectionTitle}>MISSION OVERVIEW</div>

    <div className={styles.statRow}>
      <span className={styles.statLabel}>SEA-ICE CONC.</span>
      <span className={styles.statValue}>{fmt(data.seaIceConcPct, '%')}</span>
    </div>

    <div className={styles.statRow}>
      <span className={styles.statLabel}>NEAREST ICEBERG</span>
      <span className={styles.statValue}>{fmt(data.nearestIcebergNm, ' NM')}</span>
    </div>
    <div className={styles.statSubRow}>Bearing {fmt(data.nearestIcebergBearingDeg, '°')}</div>

    <div className={styles.statRow}>
      <span className={styles.statLabel}>COMPOSITE RISK</span>
      <span className={styles.statValueLarge}>{fmt(data.compositeRisk)} /100</span>
    </div>

    <div className={styles.footerNote}>
      ICE CONC {fmt(data.iceConcChangePctPer6h, '%')}/6H NEAR CURRENT HEADING
      <br />
      AS OF {data.asOfUtc}
    </div>
  </div>
))

// ─── Sub: Risk Dashboard ────────────────────────────────────────────────────
interface RiskBarDef {
  label: string
  value: number | null
  color: string
}

const RiskDashboardSection = memo(({ data }: { data: RiskDashboardData }) => {
  const bars: RiskBarDef[] = useMemo(
    () => [
      { label: 'ICE CONCENTRATION', value: data.iceConcentrationPct, color: '#3b82c4' },
      { label: 'ICEBERG PROXIMITY', value: data.icebergProximityPct, color: '#d97b3a' },
      { label: 'WEATHER', value: data.weatherPct, color: '#2fae8a' },
    ],
    [data.iceConcentrationPct, data.icebergProximityPct, data.weatherPct]
  )

  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>RISK DASHBOARD</div>

      <div className={styles.riskScore}>
        <span className={styles.statLabel}>COMPOSITE RISK</span>
        <span className={styles.statValueLarge}>{fmt(data.compositeRisk)} /100</span>
      </div>

      {bars.map((bar) => (
        <div key={bar.label} className={styles.riskBarRow}>
          <div className={styles.riskBarHeader}>
            <span>{bar.label}</span>
            <span>{fmt(bar.value, '%')}</span>
          </div>
          <div className={styles.riskBarTrack}>
            <div
              className={styles.riskBarFill}
              style={{ width: bar.value !== null ? `${bar.value}%` : '0%', background: bar.color }}
            />
          </div>
        </div>
      ))}
    </div>
  )
})

// ─── Sub: Route Planner ─────────────────────────────────────────────────────
interface RoutePlannerSectionProps {
  data: RoutePlannerData
  onComputeRoute: (origin: string, destination: string, weighting: number) => void
}

const RoutePlannerSection = memo(({ data, onComputeRoute }: RoutePlannerSectionProps) => {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [vesselProfile, setVesselProfile] = useState(data.vesselProfiles[0] ?? '')
  const [weighting, setWeighting] = useState(50) // 0 = full safety, 100 = full fuel

  const handleWeightingChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setWeighting(Number(e.target.value))
  }, [])

  const handleCompute = useCallback(() => {
    onComputeRoute(origin, destination, weighting)
  }, [origin, destination, weighting, onComputeRoute])

  const profileOptions = useMemo(
    () => data.vesselProfiles.map((profile) => (
      <option key={profile} value={profile}>{profile}</option>
    )),
    [data.vesselProfiles]
  )

  return (
    <div className={`${styles.section} ${styles.sectionRoutePlanner}`}>
      <div className={styles.sectionTitle}>ROUTE PLANNER</div>

      <input
        type="text"
        className={styles.textInput}
        placeholder="ORIGIN — click on map or enter lat/lon"
        value={origin}
        onChange={(e) => setOrigin(e.target.value)}
      />
      <input
        type="text"
        className={styles.textInput}
        placeholder="DESTINATION — click on map or enter lat/lon"
        value={destination}
        onChange={(e) => setDestination(e.target.value)}
      />
      <select
        className={styles.selectInput}
        value={vesselProfile}
        onChange={(e) => setVesselProfile(e.target.value)}
      >
        {profileOptions}
      </select>

      <div className={styles.miniFieldRow}>
        <span>ICE CLASS <b>{data.iceClass}</b></span>
        <span>DRAFT <b>{data.draftM.toFixed(1)} m</b></span>
      </div>

      <div className={styles.weightingRow}>
        <span className={styles.weightingLabelLeft}>{100 - weighting}% SAFETY</span>
        <input
          type="range"
          className={styles.slider}
          min={0}
          max={100}
          value={weighting}
          onChange={handleWeightingChange}
        />
        <span className={styles.weightingLabelRight}>{weighting}% FUEL</span>
      </div>

      <button type="button" className={styles.computeBtn} onClick={handleCompute}>
        COMPUTE ROUTE
      </button>

      <div className={styles.computedNote}>
        Route computed — {data.routeComputedAt ?? '—'}
      </div>
    </div>
  )
})

// ─── Main Component ───────────────────────────────────────────────────────────
function BottomPanelImpl({
  selectedForecastId,
  onForecastFrameSelect,
  routePlanner,
  onComputeRoute,
  forecastFrames = MOCK_FORECAST_FRAMES,
  missionOverview = MOCK_MISSION_OVERVIEW,
  riskDashboard = MOCK_RISK_DASHBOARD,
  vesselLon,
  vesselLat,
}: BottomPanelProps) {
  return (
    <div className={styles.bottomPanel}>
      <ForecastSection
        frames={forecastFrames}
        selectedId={selectedForecastId}
        onSelect={onForecastFrameSelect}
        vesselLon={vesselLon}
        vesselLat={vesselLat}
      />
      <MissionOverviewSection data={missionOverview} />
      <RiskDashboardSection data={riskDashboard} />
      <RoutePlannerSection data={routePlanner} onComputeRoute={onComputeRoute} />
    </div>
  )
}

export const BottomPanel = memo(BottomPanelImpl)