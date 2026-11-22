import { Leaf } from 'lucide-react'
import { Brand } from './Brand'

export function SiteFooter() {
  return (
    <footer className="site-footer page-width">
      <div className="footer-glass">
        <div className="footer-left">
          <Brand compact />
          <span className="footer-rule" />
          <p>Probabilistic load intelligence for Delhi SLDC.</p>
        </div>
        <span className="footer-note">
          <Leaf aria-hidden="true" />
          Built for a resilient grid
        </span>
      </div>
    </footer>
  )
}