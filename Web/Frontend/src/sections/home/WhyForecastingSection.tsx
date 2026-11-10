import { Check } from 'lucide-react'

const benefits = [
  'Help anticipate demand peaks',
  'Support balanced energy distribution',
  'Plan for a cleaner, more resilient grid',
]

export function WhyForecastingSection() {
  return (
    <section className="why-section" aria-labelledby="why-title">
      <div className="page-width why-inner">
        <div className="why-copy">
          <span className="section-mark" />
          <p className="section-kicker">The value of looking ahead</p>
          <h2 id="why-title">
            Why Electricity
            <br />
            Forecasting Matters?
          </h2>
          <p>Accurate load forecasting helps:</p>
          <ul className="benefit-list">
            {benefits.map((benefit) => (
              <li key={benefit}>
                <span><Check aria-hidden="true" /></span>
                {benefit}
              </li>
            ))}
          </ul>
        </div>

        <figure className="forecast-visual">
          <img
            src="/forecast-delhi.svg"
            alt="Illustrated Delhi skyline with a rising electricity-demand line and forecast bars"
          />
          <figcaption>
            <span className="forecast-status">
              <span /> Forecast visualization
            </span>
            <span>Illustrative view</span>
          </figcaption>
        </figure>
      </div>
    </section>
  )
}
