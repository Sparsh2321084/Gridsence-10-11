import { Activity, ArrowRight, Layers, Shield, Zap } from 'lucide-react'

const highlights = [
  { label: 'Settlement Resolution', value: '15 Min', sub: '96 ABT blocks / day', icon: Zap },
  { label: 'Hierarchy Coverage', value: '7 Series', sub: '6 Utilities + City Total', icon: Layers },
  { label: 'Uncertainty Bounds', value: 'P05–P95', sub: 'Online ACI intervals', icon: Shield },
]

export function AboutSection() {
  return (
    <section className="home-section page-width" aria-labelledby="about-title">
      <div className="glass-card glass-card--light about-ios-shell">
        <div className="about-ios-visual">
          <img
            className="about-art"
            src="/city-grid.svg"
            alt="Connected city buildings, solar generation, and transmission infrastructure"
          />
          <div className="glass-pill glass-pill--light about-ios-caption">
            <Activity aria-hidden="true" />
            Exact energy conservation across all 6 Delhi utilities
          </div>
        </div>

        <div className="about-ios-copy">
          <p className="section-kicker">01 · About GridSense</p>
          <h2 id="about-title">
            Unified Load Intelligence for <span>Metropolitan Grids</span>
          </h2>
          <p>
            GridSense predicts 24-hour electricity demand at 15-minute resolution across Delhi&apos;s
            unbundled distribution utilities—BRPL, TPDDL, BYPL, NDMC, MES, and Northern
            Railway—while maintaining exact mathematical summation to the citywide SLDC total.
          </p>

          <div className="about-ios-pills">
            {highlights.map(({ label, value, sub, icon: Icon }) => (
              <div className="glass-tile glass-tile--light" key={label}>
                <span className="tile-icon">
                  <Icon aria-hidden="true" />
                </span>
                <div>
                  <small>{label}</small>
                  <strong>{value}</strong>
                  <span>{sub}</span>
                </div>
              </div>
            ))}
          </div>

          <a className="button button--outline" href="#how-it-works">
            Explore Architecture <ArrowRight aria-hidden="true" />
          </a>
        </div>
      </div>
    </section>
  )
}