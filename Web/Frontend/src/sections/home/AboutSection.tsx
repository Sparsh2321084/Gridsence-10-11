import { Activity, ArrowRight } from 'lucide-react'

export function AboutSection() {
  return (
    <section className="about-section page-width" aria-labelledby="about-title">
      <div className="about-art-wrap">
        <img
          className="about-art"
          src="/city-grid.svg"
          alt="Illustration of connected city buildings, renewable energy, and a power transmission tower"
        />
        <div className="art-caption">
          <span><Activity aria-hidden="true" /></span>
          A clearer view of the grid
        </div>
      </div>

      <div className="about-copy">
        <span className="section-mark" />
        <p className="section-kicker">Connected energy intelligence</p>
        <h2 id="about-title">
          About <span>GridSense</span>
        </h2>
        <p>
          GridSense is an intelligent electricity load forecasting platform designed to
          monitor Delhi&apos;s energy demand in real time and predict future load using
          cutting-edge machine learning models.
        </p>
        <p>
          By turning grid data into actionable insight, teams can plan smarter, reduce
          inefficiency, and build a more resilient energy future.
        </p>
        <a className="button button--outline" href="#how-it-works">
          Discover how it works <ArrowRight aria-hidden="true" />
        </a>
      </div>
    </section>
  )
}
