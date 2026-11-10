import { ArrowRight } from 'lucide-react'

export function HeroSection() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <img
        className="hero-art"
        src="/delhi-grid.svg"
        alt="Illustrated Delhi skyline with an electricity transmission tower at sunrise"
      />
      <div className="hero-wash" />
      <div className="hero-content page-width">
        <p className="eyebrow">
          <span className="eyebrow-dot" />
          Smarter energy starts with insight
        </p>

        <h1 id="hero-title">
          Grid<span>Sense</span>
        </h1>

        <h2>
          Smarter Electricity Forecasting
          <br className="desktop-break" />
          for a Brighter Delhi
        </h2>

        <p className="hero-description">
          Leveraging advanced machine learning to predict electricity demand,
          optimize grid management, and build a more reliable and sustainable future.
        </p>

        <a className="button button--primary" href="/dashboard">
          Explore Dashboard <ArrowRight aria-hidden="true" />
        </a>
      </div>
    </section>
  )
}
