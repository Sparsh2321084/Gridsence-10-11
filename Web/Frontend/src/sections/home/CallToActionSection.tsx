import { ArrowRight, Zap } from 'lucide-react'

export function CallToActionSection() {
  return (
    <section className="closing-cta page-width" aria-labelledby="cta-title">
      <div className="cta-tower" aria-hidden="true">
        <Zap fill="currentColor" />
      </div>

      <div className="cta-copy">
        <p className="cta-kicker">GridSense · Delhi</p>
        <h2 id="cta-title">Build a smarter, more reliable grid for Delhi</h2>
        <p>Explore real-time insights and future forecasts with GridSense.</p>
      </div>

      <a className="button button--light" href="/dashboard">
        Go to Dashboard <ArrowRight aria-hidden="true" />
      </a>
    </section>
  )
}
