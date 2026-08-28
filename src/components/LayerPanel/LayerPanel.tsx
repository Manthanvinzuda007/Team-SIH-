import React, { memo, useCallback, useMemo } from 'react'
import styles from './LayerPanel.module.css'

// ─── Types ────────────────────────────────────────────────────────────────────
export interface LayerItem {
  id: string
  label: string
  source: string
  timestamp: string
  visible: boolean
  loading?: boolean
  error?: boolean
}

export interface LayerInfo {
  name: string
  source: string
  resolution: string
  timestamp: string
  coverage: string
  dataAge: string
  status: 'CURRENT' | 'STALE' | 'UNAVAILABLE'
}

export interface DataWarning {
  id: string
  type: 'warning' | 'error' | 'info'
  title: string
  message: string
  timestamp: string
}

export interface LayerPanelProps {
  layers: LayerItem[]
  selectedLayer: LayerInfo | null
  warnings: DataWarning[]
  onLayerToggle: (id: string, visible: boolean) => void
  onLayerSelect: (id: string) => void
}

// ─── Mock Data ────────────────────────────────────────────────────────────────
export const MOCK_LAYERS: LayerItem[] = [
  { id: 'sea-ice', label: 'Sea-Ice Concentration', source: 'AMSR2', timestamp: '06:00Z', visible: true },
  { id: 'iceberg-det', label: 'Iceberg Detections', source: 'SENTINEL-1A', timestamp: '06:12Z', visible: true },
  { id: 'iceberg-drift', label: 'Iceberg Drift Corridors', source: 'SENTINEL-1A', timestamp: '06:12Z', visible: true },
  { id: 'currents', label: 'Currents (Surface)', source: 'CMEMS', timestamp: '06:00Z', visible: true },
  { id: 'wind', label: 'Wind (10m)', source: 'ERA5', timestamp: '06:00Z', visible: false },
  { id: 'bathymetry', label: 'Bathymetry', source: 'GEBCO', timestamp: '2023', visible: true },
  { id: 'risk', label: 'Risk Heatmap', source: 'MODEL', timestamp: '08:00Z', visible: true, loading: false },
  { id: 'routes', label: 'Routes', source: 'COMPUTED', timestamp: '08:40Z', visible: true },
]

export const MOCK_LAYER_INFO: LayerInfo = {
  name: 'Sea-Ice Concentration',
  source: 'AMSR2 Passive Microwave',
  resolution: '6.25 km',
  timestamp: '14 JUL 2026 06:00Z',
  coverage: 'Antarctic Region',
  dataAge: '2h 45m',
  status: 'CURRENT',
}

export const MOCK_WARNINGS: DataWarning[] = [
  {
    id: 'w1',
    type: 'warning',
    title: 'SENTINEL-1B PASS UNAVAILABLE',
    message: 'Showing last confirmed pass',
    timestamp: '06:12Z',
  },
  {
    id: 'w2',
    type: 'warning',
    title: 'WIND FORECAST +24H UNAVAILABLE',
    message: 'Showing +18H forecast',
    timestamp: '06:00Z',
  },
  {
    id: 'w3',
    type: 'info',
    title: 'NO DATA',
    message: 'Bathymetry beyond 82°S — GEBCO coverage limit',
    timestamp: '—',
  },
]

// ─── Spinner ──────────────────────────────────────────────────────────────────
const Spinner = memo(() => <span className={styles.spinner} />)

// ─── Layer Row ────────────────────────────────────────────────────────────────
interface LayerRowProps {
  item: LayerItem
  onToggle: (id: string, visible: boolean) => void
  onSelect: (id: string) => void
}

const LayerRow = memo(({ item, onToggle, onSelect }: LayerRowProps) => {
  const handleRowActivate = useCallback(() => {
    onSelect(item.id)
    onToggle(item.id, !item.visible)
  }, [item.id, item.visible, onSelect, onToggle])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        handleRowActivate()
      }
    },
    [handleRowActivate]
  )

  return (
    <div
      className={`${styles.layerRow} ${item.visible ? styles.layerRowActive : ''}`}
      onClick={handleRowActivate}
      onKeyDown={handleKeyDown}
      role="checkbox"
      aria-checked={item.visible}
      tabIndex={0}
    >
      <input
        type="checkbox"
        className={styles.checkbox}
        checked={item.visible}
        readOnly
        tabIndex={-1}
        aria-hidden="true"
      />
      <div className={styles.layerText}>
        <span className={`${styles.layerLabel} ${item.visible ? styles.layerLabelActive : ''}`}>
          {item.label}
        </span>
        <span className={styles.layerMeta}>
          {item.source} · {item.timestamp}
          {item.loading && <Spinner />}
          {item.error && <span className={styles.errorDot} />}
        </span>
      </div>
    </div>
  )
})
// ─── Layer Info ───────────────────────────────────────────────────────────────
const LayerInfoPanel = memo(({ info }: { info: LayerInfo }) => {
  const statusClass = useMemo(() => {
    if (info.status === 'CURRENT') return styles.badgeCurrent
    if (info.status === 'STALE') return styles.badgeStale
    return styles.badgeUnavailable
  }, [info.status])

  return (
    <div className={styles.infoSection}>
      <div className={styles.sectionHeader}>LAYER INFORMATION</div>
      <div className={styles.infoName}>
        {info.name}
        <span className={`${styles.badge} ${statusClass}`}>{info.status}</span>
      </div>
      <div className={styles.infoGrid}>
        <span className={styles.infoLabel}>SOURCE</span>
        <span className={styles.infoValue}>{info.source}</span>
        <span className={styles.infoLabel}>RESOLUTION</span>
        <span className={styles.infoValue}>{info.resolution}</span>
        <span className={styles.infoLabel}>TIMESTAMP</span>
        <span className={styles.infoValue}>{info.timestamp}</span>
        <span className={styles.infoLabel}>COVERAGE</span>
        <span className={styles.infoValue}>{info.coverage}</span>
        <span className={styles.infoLabel}>DATA AGE</span>
        <span className={styles.infoValue}>{info.dataAge}</span>
      </div>
    </div>
  )
})

// ─── Warning Row ──────────────────────────────────────────────────────────────
const WarningRow = memo(({ warning }: { warning: DataWarning }) => {
  const rowClass = useMemo(() => {
    if (warning.type === 'warning') return styles.warnRowWarning
    if (warning.type === 'error') return styles.warnRowError
    return styles.warnRowInfo
  }, [warning.type])

  const titleClass = useMemo(() => {
    if (warning.type === 'warning') return styles.warnTitleWarning
    if (warning.type === 'error') return styles.warnTitleError
    return styles.warnTitleInfo
  }, [warning.type])

  return (
    <div className={`${styles.warnRow} ${rowClass}`}>
      <span className={`${styles.warnTitle} ${titleClass}`}>
        {warning.type === 'warning' && '⚠ '}
        {warning.type === 'error' && '✕ '}
        {warning.type === 'info' && '· '}
        {warning.title}
      </span>
      <span className={styles.warnMessage}>{warning.message}</span>
      <span className={styles.warnTime}>{warning.timestamp}</span>
    </div>
  )
})

// ─── Main Component ───────────────────────────────────────────────────────────
const LayerPanel = memo(({
  layers,
  selectedLayer,
  warnings,
  onLayerToggle,
  onLayerSelect,
}: LayerPanelProps) => {
  const handleToggle = useCallback(
    (id: string, visible: boolean) => onLayerToggle(id, visible),
    [onLayerToggle]
  )

  const handleSelect = useCallback(
    (id: string) => onLayerSelect(id),
    [onLayerSelect]
  )

  const layerRows = useMemo(
    () =>
      layers.map(item => (
        <LayerRow
          key={item.id}
          item={item}
          onToggle={handleToggle}
          onSelect={handleSelect}
        />
      )),
    [layers, handleToggle, handleSelect]
  )

  const warningRows = useMemo(
    () => warnings.map(w => <WarningRow key={w.id} warning={w} />),
    [warnings]
  )

  return (
    <aside className={styles.panel}>
      {/* LAYERS */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>LAYERS</div>
        <div className={styles.layerList}>{layerRows}</div>
      </div>

      <div className={styles.divider} />

      {/* LAYER INFO */}
      {selectedLayer && <LayerInfoPanel info={selectedLayer} />}

      <div className={styles.divider} />

      {/* WARNINGS */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>DATA WARNINGS</div>
        <div className={styles.warnList}>{warningRows}</div>
      </div>
    </aside>
  )
})

export default LayerPanel