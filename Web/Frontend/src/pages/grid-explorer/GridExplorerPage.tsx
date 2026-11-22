import { ArrowLeft, Compass, Layers, MapPin, Sparkles } from 'lucide-react'

const DELHI_ZONES = [
  {
    code: 'BRPL',
    name: 'BSES Rajdhani Power Ltd',
    region: 'South & West Delhi',
    share: '~41%',
    driver: 'Late-night residential cooling & commercial corridors',
  },
  {
    code: 'TPDDL',
    name: 'Tata Power Delhi Distribution',
    region: 'North & North-West Delhi',
    share: '~31%',
    driver: 'Industrial feeders, residential colonies & rooftop solar',
  },
  {
    code: 'BYPL',
    name: 'BSES Yamuna Power Ltd',
    region: 'East & Central Delhi',
    share: '~22%',
    driver: 'High-density urban residential & evening AC surge',
  },
  {
    code: 'NDMC',
    name: 'New Delhi Municipal Council',
    region: 'Lutyens & Central Diplomatic Zone',
    share: '~4.5%',
    driver: 'Afternoon office HVAC peak (14:45–15:15 IST)',
  },
  {
    code: 'MES',
    name: 'Military Engineer Services',
    region: 'Delhi Cantonment',
    share: '~0.7%',
    driver: 'Institutional & defense base load schedule',
  },
  {
    code: 'Railways',
    name: 'Northern Railway Traction',
    region: 'Delhi Suburban & Trunk Rail Corridors',
    share: '~0.3%',
    driver: 'Timetable-driven electric traction drawal',
  },
]

export function GridExplorerPage() {
  return (
    <div className="home-glass-canvas explorer-placeholder-page">
      <div className="ambient-orb ambient-orb--one" aria-hidden="true" />
      <div className="ambient-orb ambient-orb--two" aria-hidden="true" />

      <div className="page-width">
        <div className="glass-card glass-card--dark explorer-placeholder-card">
          <div className="glass-pill glass-pill--dark">
            <Compass aria-hidden="true" /> Interactive Spatial Topology · Coming Next
          </div>

          <h1>
            Delhi <span>Grid Explorer</span>
          </h1>

          <p>
            Interactive 3D spatial map of Delhi&apos;s six unbundled distribution utilities,
            coincident peak clocks, and 220 kV / 400 kV transmission corridors—reconciled into
            Delhi SLDC&apos;s citywide total.
          </p>

          <div className="explorer-zone-grid" style={{ marginBottom: 24 }}>
            {DELHI_ZONES.map((zone) => (
              <div className="glass-subcard glass-subcard--dark explorer-zone-pill" key={zone.code}>
                <div className="zone-pill-top">
                  <MapPin aria-hidden="true" />
                  <strong>{zone.code}</strong>
                  <span>{zone.share}</span>
                </div>
                <small>{zone.region}</small>
                <p style={{ marginTop: 4 }}>{zone.driver}</p>
              </div>
            ))}
          </div>

          <div className="explorer-placeholder-actions">
            <a className="button button--primary" href="/dashboard">
              <Sparkles aria-hidden="true" /> Open Live Forecast Dashboard
            </a>
            <a className="button button--glass-dark" href="/">
              <ArrowLeft aria-hidden="true" /> Back to Home
            </a>
            <span className="glass-pill glass-pill--dark" style={{ marginLeft: 'auto' }}>
              <Layers aria-hidden="true" /> 7 MinT-Reconciled Entities
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default GridExplorerPage