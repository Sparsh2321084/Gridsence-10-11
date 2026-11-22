import { Brand } from './Brand'
import type { ActivePage } from './SiteLayout'

export function SiteHeader({ activePage = 'home' }: { activePage?: ActivePage }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Brand />
        <nav className="main-nav" aria-label="Main navigation">
          <a className={activePage === 'home' ? 'active' : ''} href="/">
            Home
          </a>
          <a className={activePage === 'dashboard' ? 'active' : ''} href="/dashboard">
            Dashboard
          </a>
          <a className={activePage === 'grid-explorer' ? 'active' : ''} href="/grid-explorer">
            Explorer
          </a>
        </nav>
      </div>
    </header>
  )
}