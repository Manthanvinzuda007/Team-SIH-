import { memo, useState, useCallback, useMemo } from 'react'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'
import styles from './RoutePanel.module.css'

// ─── Types ────────────────────────────────────────────────────────────────────

export type RouteType = 'FASTEST' | 'SAFEST' | 'BALANCED'
export type IcebergSize = 'LARGE' | 'MEDIUM' | 'SMALL' | 'UNCONFIRMED'

export interface RouteRow {
  type: RouteType
  distNm: number | null
  etaUtc: string | null
  fuelT: number | null
  iceEncounters: number | null
  riskScore: number | null
}

export interface IcebergRow {
  id: string
  size: IcebergSize
  lat: string
  lon: string
  spdKn: number | null
  hdgDeg: number | null
  lastSeen: string
  unconfirmed?: boolean
}

export interface IcebergDetail {
  id: string
  classLabel: IcebergSize
  lengthM: number | null
  confidencePct: number | null
  corridorKm: number | null
  trackPoints: { t: number; historical: number | null; predicted: number | null }[]
}

export interface RoutePanelProps {
  routes?: RouteRow[]
  selectedRoute?: RouteType
  icebergs?: IcebergRow[]
  selectedIcebergId?: string
  icebergDetail?: IcebergDetail | null
  alphaRisk?: number | null
  betaFuel?: number | null
  gammaDistance?: number | null
  onRouteSelect?: (type: RouteType) => void
  onIcebergSelect?: (id: string) => void
}

// ─── Mock Data ────────────────────────────────────────────────────────────────

export const MOCK_ROUTES: RouteRow[] = [
  { type: 'FASTEST', distNm: 312, etaUtc: '18:42Z', fuelT: 84, iceEncounters: 3, riskScore: 67 },
  { type: 'SAFEST', distNm: 341, etaUtc: '20:15Z', fuelT: 91, iceEncounters: 0, riskScore: 12 },
  { type: 'BALANCED', distNm: 324, etaUtc: '19:20Z', fuelT: 87, iceEncounters: 1, riskScore: 31 },
]

export const MOCK_ICEBERGS: IcebergRow[] = [
  { id: 'IBG-231', size: 'LARGE', lat: '70°12.3\' S', lon: '045°21.7\' E', spdKn: 1.2, hdgDeg: 247, lastSeen: '14 JUL 06:12Z' },
  { id: 'IBG-232', size: 'MEDIUM', lat: '70°18.9\' S', lon: '045°15.2\' E', spdKn: 0.8, hdgDeg: 231, lastSeen: '14 JUL 06:12Z' },
  { id: 'IBG-233', size: 'SMALL', lat: '70°25.4\' S', lon: '045°33.1\' E', spdKn: 1.4, hdgDeg: 259, lastSeen: '14 JUL 06:12Z' },
  { id: 'IBG-234', size: 'UNCONFIRMED', lat: '70°31.0\' S', lon: '045°40.6\' E', spdKn: null, hdgDeg: null, lastSeen: '14 JUL 06:12Z', unconfirmed: true },
]

export const MOCK_ICEBERG_DETAIL: IcebergDetail = {
  id: 'IBG-231',
  classLabel: 'LARGE',
  lengthM: 1840,
  confidencePct: 87,
  corridorKm: 12,
  trackPoints: [
    { t: -6, historical: 0, predicted: null },
    { t: -4, historical: 1.2, predicted: null },
    { t: -2, historical: 2.1, predicted: null },
    { t: 0, historical: 2.8, predicted: 2.8 },
    { t: 2, historical: null, predicted: 3.9 },
    { t: 4, historical: null, predicted: 5.2 },
    { t: 6, historical: null, predicted: 6.8 },
  ],
}

// ─── Route colour map ─────────────────────────────────────────────────────────
const ROUTE_COLOR: Record<RouteType, string> = {
  FASTEST: '#8a6a10',
  SAFEST: '#1a5a2a',
  BALANCED: '#3a4a5a',
}

const ROUTE_ACTIVE_COLOR: Record<RouteType, string> = {
  FASTEST: '#c9a030',
  SAFEST: '#3a9a4a',
  BALANCED: '#7a8a9a',
}

// ─── Sub: Route Row ───────────────────────────────────────────────────────────
interface RouteRowItemProps {
  row: RouteRow
  isSelected: boolean
  onSelect: (type: RouteType) => void
}

const RouteRowItem = memo(({ row, isSelected, onSelect }: RouteRowItemProps) => {
  const color = isSelected ? ROUTE_ACTIVE_COLOR[row.type] : ROUTE_COLOR[row.type]
  return (
    <tr
      className={`${styles.tableRow} ${isSelected ? styles.tableRowActive : ''}`}
      onClick={() => onSelect(row.type)}
      style={{ borderLeft: `2px solid ${color}` }}
    >
      <td className={styles.routeTypeCell} style={{ color }}>
        {row.type}
      </td>
      <td className={styles.td}>{row.distNm ?? '—'}</td>
      <td className={styles.td}>{row.etaUtc ?? '—'}</td>
      <td className={styles.td}>{row.fuelT ?? '—'}</td>
      <td className={styles.td}>{row.iceEncounters ?? '—'}</td>
      <td className={styles.tdRisk} style={{ color: row.riskScore !== null ? (row.riskScore > 60 ? '#8a2020' : row.riskScore > 30 ? '#8a6020' : '#3a8a3a') : '#5a7a8a' }}>
        {row.riskScore ?? '—'}
      </td>
    </tr>
  )
})

// ─── Sub: Iceberg Row ─────────────────────────────────────────────────────────
interface IcebergRowItemProps {
  row: IcebergRow
  isSelected: boolean
  onSelect: (id: string) => void
}

const IcebergRowItem = memo(({ row, isSelected, onSelect }: IcebergRowItemProps) => (
  <tr
    className={`${styles.tableRow} ${isSelected ? styles.tableRowActive : ''} ${row.unconfirmed ? styles.tableRowUnconfirmed : ''}`}
    onClick={() => onSelect(row.id)}
  >
    <td className={styles.td} style={{ color: row.unconfirmed ? '#8a3030' : '#6a8aaa' }}>{row.id}</td>
    <td className={styles.td}>
      {row.unconfirmed
        ? <span className={styles.unconfirmedBadge}>UNCONFIRMED CANDIDATE</span>
        : row.size}
    </td>
    <td className={styles.tdSmall}>{row.lat}<br />{row.lon}</td>
    <td className={styles.td}>{row.spdKn ?? '—'}</td>
    <td className={styles.td}>{row.hdgDeg !== null ? `${row.hdgDeg}°` : '—'}</td>
    <td className={styles.tdSmall}>{row.lastSeen}</td>
  </tr>
))

// ─── Sub: Iceberg Detail ──────────────────────────────────────────────────────
const IcebergDetailPanel = memo(({ detail }: { detail: IcebergDetail }) => (
  <div className={styles.detailPanel}>
    <div className={styles.detailHeader}>SELECTED: {detail.id}</div>
    <div className={styles.detailBody}>
      <div className={styles.detailChart}>
        <ResponsiveContainer width="100%" height={60}>
          <LineChart data={detail.trackPoints}>
            <Line
              type="monotone"
              dataKey="historical"
              stroke="#4a6a8a"
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="predicted"
              stroke="#4a6a8a"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              connectNulls={false}
            />
            <Tooltip
              contentStyle={{ background: '#070c14', border: '1px solid #0d1e30', fontSize: 8, color: '#6a8aaa' }}
              labelFormatter={(v) => `T${v}h`}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className={styles.chartLegend}>
          <span className={styles.legendHistorical}>— HISTORICAL</span>
          <span className={styles.legendPredicted}>- - PREDICTED</span>
        </div>
      </div>
      <div className={styles.detailGrid}>
        <span className={styles.detailLabel}>CLASS</span>
        <span className={styles.detailValue}>{detail.classLabel}</span>
        <span className={styles.detailLabel}>LENGTH</span>
        <span className={styles.detailValue}>{detail.lengthM !== null ? `${detail.lengthM} m` : '—'}</span>
        <span className={styles.detailLabel}>CONFIDENCE</span>
        <span className={styles.detailValue}>{detail.confidencePct !== null ? `${detail.confidencePct} %` : '—'}</span>
        <span className={styles.detailLabel}>CORRIDOR</span>
        <span className={styles.detailValue}>{detail.corridorKm !== null ? `± ${detail.corridorKm} km` : '—'}</span>
      </div>
    </div>
  </div>
))

// ─── Sub: Why This Route (rebuilt with weight bars) ───────────────────────────
interface WeightDef {
  greek: string
  label: string
  value: number | null
  color: string
}

const WhyThisRoute = memo(({ alpha, beta, gamma }: { alpha: number | null; beta: number | null; gamma: number | null }) => {
  const hasWeights = alpha !== null && beta !== null && gamma !== null

  const weights: WeightDef[] = [
    { greek: 'α', label: 'Risk', value: alpha, color: '#8a2020' },
    { greek: 'β', label: 'Fuel', value: beta, color: '#8a6020' },
    { greek: 'γ', label: 'Distance', value: gamma, color: '#2a5a8a' },
  ]

  return (
    <div className={styles.whySection}>
      <div className={styles.sectionHeader}>WHY THIS ROUTE</div>
      <div className={styles.whyBody}>
        <p className={styles.whyNote}>
          {hasWeights ? 'Weighted cost optimized using:' : 'Weighting appears once a route is computed.'}
        </p>
        {weights.map((w) => (
          <div key={w.label} className={styles.whyRow}>
            <div className={styles.whyRowHeader}>
              <span className={styles.whyGreek}>{w.greek}</span>
              <span className={styles.whyLabel}>{w.label}</span>
              <span className={styles.whyVal}>{w.value !== null ? w.value.toFixed(2) : '—'}</span>
            </div>
            <div className={styles.whyBarTrack}>
              <div
                className={styles.whyBarFill}
                style={{ width: w.value !== null ? `${Math.min(100, w.value * 100)}%` : '0%', background: w.color }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
})

// ─── Main Component ───────────────────────────────────────────────────────────
const RoutePanel = memo(({
  routes = MOCK_ROUTES,
  selectedRoute = 'BALANCED',
  icebergs = MOCK_ICEBERGS,
  selectedIcebergId = 'IBG-231',
  icebergDetail = MOCK_ICEBERG_DETAIL,
  alphaRisk = null,
  betaFuel = null,
  gammaDistance = null,
  onRouteSelect,
  onIcebergSelect,
}: RoutePanelProps) => {

  const [activeRoute, setActiveRoute] = useState<RouteType>(selectedRoute)
  const [activeIceberg, setActiveIceberg] = useState<string>(selectedIcebergId)

  const handleRouteSelect = useCallback((type: RouteType) => {
    setActiveRoute(type)
    onRouteSelect?.(type)
  }, [onRouteSelect])

  const handleIcebergSelect = useCallback((id: string) => {
    setActiveIceberg(id)
    onIcebergSelect?.(id)
  }, [onIcebergSelect])

  const routeRows = useMemo(() =>
    routes.map(r => (
      <RouteRowItem
        key={r.type}
        row={r}
        isSelected={activeRoute === r.type}
        onSelect={handleRouteSelect}
      />
    )), [routes, activeRoute, handleRouteSelect])

  const icebergRows = useMemo(() =>
    icebergs.map(b => (
      <IcebergRowItem
        key={b.id}
        row={b}
        isSelected={activeIceberg === b.id}
        onSelect={handleIcebergSelect}
      />
    )), [icebergs, activeIceberg, handleIcebergSelect])

  return (
    <aside className={styles.panel}>

      {/* ── ROUTE COMPARISON ── */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>ROUTE COMPARISON</div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>ROUTE</th>
                <th className={styles.th}>DIST (NM)</th>
                <th className={styles.th}>ETA (UTC)</th>
                <th className={styles.th}>FUEL (t)</th>
                <th className={styles.th}>ICE</th>
                <th className={styles.th}>RISK</th>
              </tr>
            </thead>
            <tbody>{routeRows}</tbody>
          </table>
        </div>
      </div>

      <div className={styles.divider} />

      {/* ── ICEBERG MONITORING ── */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>ICEBERG MONITORING</div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>ID</th>
                <th className={styles.th}>SIZE</th>
                <th className={styles.th}>POSITION</th>
                <th className={styles.th}>SPD</th>
                <th className={styles.th}>HDG</th>
                <th className={styles.th}>SEEN</th>
              </tr>
            </thead>
            <tbody>{icebergRows}</tbody>
          </table>
        </div>
        {icebergDetail && activeIceberg && <IcebergDetailPanel detail={icebergDetail} />}
      </div>

      <div className={styles.divider} />

      {/* ── WHY THIS ROUTE ── */}
      <WhyThisRoute alpha={alphaRisk} beta={betaFuel} gamma={gammaDistance} />

    </aside>
  )
})

export default RoutePanel