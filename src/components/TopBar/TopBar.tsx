import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import styles from './TopBar.module.css'

export type DataFreshness = 'CURRENT' | 'STALE' | 'NO DATA'

export interface VesselData {
  vesselName: string
  iceClass: string
  lat: number
  lon: number
  heading: number
  speedKnots: number
  dataFreshness: DataFreshness
  dataSources: string[]
}

export interface TopBarProps {
  data: VesselData
  onMenuClick?: () => void
}

export const MOCK_VESSEL_DATA: VesselData = {
  vesselName: 'RV AURORA',
  iceClass: 'PC6',
  lat: -(70 + 21.534 / 60),
  lon: 45 + 18.925 / 60,
  heading: 132.6,
  speedKnots: 12.4,
  dataFreshness: 'CURRENT',
  dataSources: [
    'AMSR2 06:00Z',
    'S1A 06:12Z',
    'ERA5 06:00Z',
    'CMEMS 06:00Z',
    'GEBCO 2023',
  ],
}

const MONTHS = [
  'JAN',
  'FEB',
  'MAR',
  'APR',
  'MAY',
  'JUN',
  'JUL',
  'AUG',
  'SEP',
  'OCT',
  'NOV',
  'DEC',
] as const

function formatUtc(now: Date) {
  const day = String(now.getUTCDate()).padStart(2, '0')
  const month = MONTHS[now.getUTCMonth()]
  const year = now.getUTCFullYear()
  const hh = String(now.getUTCHours()).padStart(2, '0')
  const mm = String(now.getUTCMinutes()).padStart(2, '0')
  const ss = String(now.getUTCSeconds()).padStart(2, '0')

  return {
    date: `${day} ${month} ${year}`,
    time: `${hh}:${mm}:${ss}`,
  }
}

function formatCoord(value: number, axis: 'lat' | 'lon') {
  const abs = Math.abs(value)
  const degrees = Math.floor(abs)
  const minutes = (abs - degrees) * 60
  const hemi =
    axis === 'lat' ? (value >= 0 ? 'N' : 'S') : value >= 0 ? 'E' : 'W'
  const degStr =
    axis === 'lat' ? String(degrees) : String(degrees).padStart(3, '0')

  return `${degStr}° ${minutes.toFixed(3)}' ${hemi}`
}

const UtcClock = memo(function UtcClock() {
  const [utc, setUtc] = useState(() => formatUtc(new Date()))

  useEffect(() => {
    const id = window.setInterval(() => {
      setUtc(formatUtc(new Date()))
    }, 1000)

    return () => window.clearInterval(id)
  }, [])

  return (
    <div className={styles.clock}>
      <span className={styles.label}>UTC</span>
      <span className={styles.date}>{utc.date}</span>
      <time className={styles.time} dateTime={utc.time}>
        {utc.time}
      </time>
    </div>
  )
})

function TopBar({ data, onMenuClick }: TopBarProps) {
  const handleMenuClick = useCallback(() => {
    onMenuClick?.()
  }, [onMenuClick])

  const formatted = useMemo(
    () => ({
      lat: formatCoord(data.lat, 'lat'),
      lon: formatCoord(data.lon, 'lon'),
      heading: `${data.heading.toFixed(1)}°`,
      speed: `${data.speedKnots.toFixed(1)} kn`,
    }),
    [data.lat, data.lon, data.heading, data.speedKnots],
  )

  const freshnessClass =
    data.dataFreshness === 'CURRENT'
      ? styles.freshCurrent
      : data.dataFreshness === 'STALE'
        ? styles.freshStale
        : styles.freshNone

  return (
    <header className={styles.bar} aria-label="Polaris navigation top bar">
      <div className={styles.left}>
        <div className={styles.brand}>
          <span className={styles.brandTitle}>POLARIS</span>
          <span className={styles.brandSub}>NAVIGATION SUITE</span>
        </div>
        <div className={styles.divider} aria-hidden="true" />
        <div className={styles.vessel}>
          <span className={styles.vesselName}>{data.vesselName}</span>
          <span className={styles.iceClass}>Ice Class: {data.iceClass}</span>
        </div>
      </div>

      <div className={styles.coords}>
        <div className={styles.coordRow}>
          <span className={styles.label}>LAT</span>
          <span className={styles.coordValue}>{formatted.lat}</span>
        </div>
        <div className={styles.coordRow}>
          <span className={styles.label}>LON</span>
          <span className={styles.coordValue}>{formatted.lon}</span>
        </div>
      </div>

      <UtcClock />

      <div className={styles.metrics}>
        <div className={styles.metric}>
          <span className={styles.label}>HDG</span>
          <span className={styles.value}>{formatted.heading}</span>
        </div>
        <div className={styles.metric}>
          <span className={styles.label}>SPD</span>
          <span className={styles.value}>{formatted.speed}</span>
        </div>
        <div className={styles.metric}>
          <span className={styles.label}>DATA FRESHNESS</span>
          <span className={`${styles.freshness} ${freshnessClass}`}>
            <span className={styles.dot} aria-hidden="true" />
            {data.dataFreshness}
          </span>
        </div>
      </div>

      <div className={styles.sources}>
        <span className={styles.label}>DATA SOURCES</span>
        <ul className={styles.sourceGrid}>
          {data.dataSources.map((source) => (
            <li key={source}>{source}</li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        className={styles.menu}
        aria-label="Open menu"
        onClick={handleMenuClick}
      >
        MENU
        <span className={styles.hamburger} aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
      </button>
    </header>
  )
}

export default memo(TopBar)
