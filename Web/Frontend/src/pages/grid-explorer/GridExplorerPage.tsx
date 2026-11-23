import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Clock3, MapPin, RefreshCw, Search, Zap } from 'lucide-react'
import { apiUrl } from '../../lib/api'
import { DelhiGridMap } from './DelhiGridMap'
import { DELHI_GRID_REGIONS, type UtilitySeriesKey } from './delhiGridTopology'

export function GridExplorerPage() {
  const [selectedId, setSelectedId] = useState<UtilitySeriesKey>('brpl_mw')
  const [latestRow, setLatestRow] = useState<Record<string, unknown> | null>(null)
  const [query, setQuery] = useState('')
  const [showSubstations, setShowSubstations] = useState(true)
  const [showCorridors, setShowCorridors] = useState(true)
  const [showLandmarks, setShowLandmarks] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const loadForecast = (signal?: AbortSignal) => {
    setRefreshing(true)
    return fetch(apiUrl('/api/forecast'), signal ? { signal } : undefined)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.forecast) && data.forecast.length > 0) {
          setLatestRow(data.forecast[0])
        }
      })
      .catch(() => {})
      .finally(() => setRefreshing(false))
  }

  useEffect(() => {
    const controller = new AbortController()
    void loadForecast(controller.signal)
    return () => controller.abort()
  }, [])

  const activeRegion = useMemo(
    () => DELHI_GRID_REGIONS.find((r) => r.id === selectedId) ?? DELHI_GRID_REGIONS[0],
    [selectedId],
  )

  const liveMw = latestRow?.[activeRegion.id]
  const filteredRegions = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return DELHI_GRID_REGIONS
    return DELHI_GRID_REGIONS.filter((region) =>
      `${region.code} ${region.name} ${region.zoneLabel}`.toLowerCase().includes(normalized),
    )
  }, [query])

  return (
    <main className="grid-explorer-page">
      <div className="page-width">
        <header className="grid-explorer-heading">
          <div>
            <p className="section-kicker">National Capital Territory</p>
            <h1>Delhi Grid Explorer</h1>
            <p>Explore distribution zones, substations and live forecast load across the capital.</p>
          </div>
          <button
            className="grid-refresh-button"
            type="button"
            onClick={() => void loadForecast()}
            disabled={refreshing}
          >
            <RefreshCw className={refreshing ? 'grid-spinner' : ''} aria-hidden="true" />
            Refresh forecast
          </button>
        </header>

        <section className="grid-explorer-shell">
          <aside className="grid-explorer-sidebar">
            <label className="grid-region-search">
              <Search aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search Delhi zone"
                aria-label="Search Delhi zone"
              />
            </label>

            <div className="grid-region-list">
              {filteredRegions.map((region) => (
                <button
                  key={region.id}
                  type="button"
                  className={`grid-region-item ${selectedId === region.id ? 'is-active' : ''}`}
                  onClick={() => setSelectedId(region.id)}
                >
                  <span className="grid-region-dot" style={{ background: region.accent }} />
                  <span>
                    <strong>{region.code}</strong>
                    <small>{region.zoneLabel}</small>
                  </span>
                  <b>{region.sharePct}</b>
                </button>
              ))}
              {filteredRegions.length === 0 && (
                <p className="grid-region-empty">No matching zones</p>
              )}
            </div>

            <div className="grid-layer-controls">
              <p>Map layers</p>
              <button type="button" className={showSubstations ? 'is-on' : ''} onClick={() => setShowSubstations((value) => !value)}>
                Substations
              </button>
              <button type="button" className={showCorridors ? 'is-on' : ''} onClick={() => setShowCorridors((value) => !value)}>
                Corridors
              </button>
              <button type="button" className={showLandmarks ? 'is-on' : ''} onClick={() => setShowLandmarks((value) => !value)}>
                Landmarks
              </button>
            </div>
          </aside>

          <div className="grid-map-panel">
            <DelhiGridMap
              selectedRegionId={selectedId}
              onSelectRegion={setSelectedId}
              latestForecastRow={latestRow}
              showSubstations={showSubstations}
              showCorridors={showCorridors}
              showLandmarks={showLandmarks}
            />
          </div>

          <aside className="grid-detail-panel" style={{ '--region-accent': activeRegion.accent } as CSSProperties}>
            <div className="grid-detail-status">
              <span style={{ background: activeRegion.accent }} />
              Active zone
            </div>
            <p className="grid-detail-code">{activeRegion.code}</p>
            <h2>{activeRegion.name}</h2>
            <p className="grid-detail-zone"><MapPin aria-hidden="true" /> {activeRegion.zoneLabel}</p>

            <div className="grid-live-metric">
              <div>
                <small><Zap aria-hidden="true" /> Forecast load</small>
                <strong>{typeof liveMw === 'number' ? liveMw.toFixed(1) : '—'} MW</strong>
              </div>
              <span>{activeRegion.sharePct} share</span>
            </div>

            <dl className="grid-detail-facts">
              <div>
                <dt>Archetype</dt>
                <dd>{activeRegion.archetype}</dd>
              </div>
              <div>
                <dt><Clock3 aria-hidden="true" /> Peak window</dt>
                <dd>{activeRegion.peakWindow}</dd>
              </div>
            </dl>

            <div className="grid-substation-list">
              <h3>Key substations</h3>
              {activeRegion.innerSubstations.slice(0, 4).map((sub) => (
                <div key={sub.id}>
                  <span />
                  <p>
                    <strong>{sub.name}</strong>
                    <small>{sub.voltage}</small>
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </section>
      </div>
    </main>
  )
}

export default GridExplorerPage