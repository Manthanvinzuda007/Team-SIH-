import { useState, useCallback, useMemo } from 'react'

import TopBar, {
  MOCK_VESSEL_DATA,
} from './components/TopBar/TopBar'

import LayerPanel, {
  MOCK_LAYERS,
  MOCK_LAYER_INFO,
  MOCK_WARNINGS,
  type LayerItem,
} from './components/LayerPanel/LayerPanel'

import RoutePanel, {
  MOCK_ICEBERGS,
  MOCK_ROUTES,
  type RouteRow,
  type RouteType,
} from './components/RoutePanel/RoutePanel'

import {
  BottomPanel,
  type ForecastFrame,
} from './components/BottomPanel/BottomPanel'

import { TimeController } from './components/TimeController/TimeController'

import MapView, {
  type MapRoute,
  type VesselPosition,
} from './components/MapView/MapView'

import styles from './App.module.css'
import './index.css'

function App() {
  const [layers, setLayers] =
    useState<LayerItem[]>(MOCK_LAYERS)

  const [selectedRoute, setSelectedRoute] =
    useState<RouteType>('BALANCED')

  const [routes, setRoutes] =
    useState<RouteRow[]>(MOCK_ROUTES)

  const [computedAt, setComputedAt] =
    useState<string | null>(null)

  const [forecastFrame, setForecastFrame] =
    useState('current')

  const [mobilePanel, setMobilePanel] =
    useState<'layers' | 'mission' | null>(null)

  const vessel: VesselPosition = useMemo(
    () => ({
      longitude: 45.315,
      latitude: -70.359,
      heading: 132.6,
      speedKnots: 12.4,
    }),
    []
  )

  const mapRoutes: MapRoute[] = useMemo(
    () => [
      {
        type: 'FASTEST',
        coordinates: [
          [45.315, -70.359],
          [44.8, -71],
          [44.1, -71.55],
          [43.2, -72.05],
          [42.4, -72.25],
        ],
      },
      {
        type: 'SAFEST',
        coordinates: [
          [45.315, -70.359],
          [46.25, -70.95],
          [46, -71.7],
          [44.7, -72.45],
          [42.4, -72.25],
        ],
      },
      {
        type: 'BALANCED',
        coordinates: [
          [45.315, -70.359],
          [45.45, -71.12],
          [44.85, -71.8],
          [43.8, -72.22],
          [42.4, -72.25],
        ],
      },
    ],
    []
  )

  const handleToggle = useCallback(
    (id: string, visible: boolean) => {
      setLayers((prev) =>
        prev.map((layer) =>
          layer.id === id
            ? { ...layer, visible }
            : layer
        )
      )
    },
    []
  )

  const handleSelect = useCallback(
    (id: string) => {
      console.log('selected layer:', id)
    },
    []
  )

  const handleComputeRoute = useCallback(
    (
      _origin: string,
      _destination: string,
      weighting: number
    ) => {
      const safetyBias =
        (100 - weighting) / 100

      setRoutes(
        MOCK_ROUTES.map((route) => ({
          ...route,
          riskScore: Math.max(
            5,
            Math.round(
              (route.riskScore ?? 0) *
                (1 - safetyBias * 0.18)
            )
          ),
        }))
      )

      setComputedAt(
        new Date()
          .toUTCString()
          .replace('GMT', 'UTC')
      )

      setSelectedRoute(
        weighting < 35
          ? 'SAFEST'
          : weighting > 70
            ? 'FASTEST'
            : 'BALANCED'
      )
    },
    []
  )

  const toggleMobilePanel = useCallback(
    (panel: 'layers' | 'mission') => {
      setMobilePanel((current) =>
        current === panel
          ? null
          : panel
      )
    },
    []
  )

  return (
    <div className={styles.root}>

      {/* =====================================================
          TOP BAR
      ===================================================== */}

      <header className={styles.topbar}>
        <TopBar
          data={MOCK_VESSEL_DATA}
          onMenuClick={() =>
            toggleMobilePanel('layers')
          }
        />
      </header>


      {/* =====================================================
          MAIN WORKSPACE
      ===================================================== */}

      <div className={styles.middle}>

        {/* ================= LEFT SIDEBAR ================= */}

        <aside
          className={`${styles.left} ${
            mobilePanel === 'layers'
              ? styles.mobilePanelOpen
              : ''
          }`}
        >
          <LayerPanel
            layers={layers}
            selectedLayer={MOCK_LAYER_INFO}
            warnings={MOCK_WARNINGS}
            onLayerToggle={handleToggle}
            onLayerSelect={handleSelect}
          />
        </aside>


        {/* ================= CENTER + RIGHT ================= */}

        <div className={styles.dashboardGrid}>

          {/* ================= MAP ================= */}

          <main className={styles.map}>
            <MapView
              layers={layers}
              vessel={vessel}
              routes={mapRoutes}
              selectedRoute={selectedRoute}
              forecastFrame={forecastFrame}
            />

            <div className={styles.mobileControls}>
              <button
                type="button"
                onClick={() =>
                  toggleMobilePanel('layers')
                }
              >
                LAYERS
              </button>

              <button
                type="button"
                onClick={() =>
                  toggleMobilePanel('mission')
                }
              >
                MISSION
              </button>
            </div>
          </main>


          {/* ================= RIGHT UPPER PANEL ================= */}

          <aside
            className={`${styles.right} ${
              mobilePanel === 'mission'
                ? styles.mobilePanelOpen
                : ''
            }`}
          >
            <RoutePanel
              routes={routes}
              selectedRoute={selectedRoute}
              icebergs={MOCK_ICEBERGS}
              alphaRisk={0.55}
              betaFuel={0.25}
              gammaDistance={0.20}
              onRouteSelect={setSelectedRoute}
            />
          </aside>


          {/* ================= LOWER DASHBOARD ================= */}

          <section className={styles.bottom}>
            <BottomPanel
              selectedForecastId={forecastFrame}
              onForecastFrameSelect={(
                frame: ForecastFrame
              ) =>
                setForecastFrame(frame.id)
              }
              routePlanner={{
                vesselProfiles: [
                  'RV Aurora — PC6',
                  'Icebreaker — PC3',
                  'Cargo — PC7',
                ],
                iceClass: 'PC6',
                draftM: 8.2,
                routeComputedAt:
                  computedAt,
              }}
              onComputeRoute={
                handleComputeRoute
              }
            />
          </section>

        </div>
      </div>


      {/* =====================================================
          TIME CONTROLLER
      ===================================================== */}

      <footer className={styles.time}>
        <TimeController />
      </footer>

    </div>
  )
}

export default App