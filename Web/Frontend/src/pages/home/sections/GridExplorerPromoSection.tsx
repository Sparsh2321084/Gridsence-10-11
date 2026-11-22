import { ArrowRight, Compass, MapPin } from 'lucide-react'

const utilities = [
  { name: 'BRPL', zone: 'South & West Delhi', share: '42.5%' },
  { name: 'TPDDL', zone: 'North & North-West', share: '30.6%' },
  { name: 'BYPL', zone: 'Central & East Delhi', share: '21.8%' },
  { name: 'NDMC', zone: 'Lutyens Core', share: '3.9%' },
  { name: 'MES', zone: 'Cantonment', share: '0.7%' },
  { name: 'Railways', zone: '25 kV Traction', share: '0.4%' },
]

export function GridExplorerPromoSection() {
  return (
    <section className="home-section page-width" aria-labelledby="explorer-promo-title">
      <div className="glass-card glass-card--dark explorer-promo-card">
        <div className="explorer-promo-copy">
          <span className="glass-pill glass-pill--dark">
            <Compass aria-hidden="true" /> Interactive Territory View
          </span>
          <h2 id="explorer-promo-title">Explore Delhi&apos;s Six Utility Zones</h2>
          <p>
            Inspect zone-level load archetypes, peak timing asynchrony, and boundary shares across
            every distribution licensee in the National Capital Territory.
          </p>
          <a className="button button--primary" href="/grid-explorer">
            Launch Grid Explorer <ArrowRight aria-hidden="true" />
          </a>
        </div>

        <div className="explorer-zone-grid">
          {utilities.map((u) => (
            <div className="glass-subcard glass-subcard--dark explorer-zone-pill" key={u.name}>
              <div className="zone-pill-top">
                <MapPin aria-hidden="true" />
                <strong>{u.name}</strong>
                <span>{u.share}</span>
              </div>
              <small>{u.zone}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}