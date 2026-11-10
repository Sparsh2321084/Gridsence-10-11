import { Leaf } from 'lucide-react'
import { Brand } from './Brand'

export function SiteFooter() {
  return (
    <footer className="site-footer page-width">
      <Brand compact />
      <span className="footer-rule" />
      <p>Smarter insights. A stronger grid.</p>
      <span className="footer-note">
        <Leaf aria-hidden="true" />
        Built for a brighter Delhi
      </span>
    </footer>
  )
}
