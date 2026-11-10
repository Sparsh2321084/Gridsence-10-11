import { Brand } from './Brand'

export function SiteHeader({ dashboard = false }: { dashboard?: boolean }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <Brand />
        <nav className="main-nav" aria-label="Main navigation">
          <a className={!dashboard ? 'active' : ''} href="/">Home</a>
          <a className={dashboard ? 'active' : ''} href="/dashboard">Dashboard</a>
        </nav>
      </div>
    </header>
  )
}
