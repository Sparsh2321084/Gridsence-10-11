import type { ReactNode } from 'react'
import { SiteFooter } from './SiteFooter'
import { SiteHeader } from './SiteHeader'

type SiteLayoutProps = {
  activePage: 'home' | 'dashboard'
  children: ReactNode
}

export function SiteLayout({ activePage, children }: SiteLayoutProps) {
  return (
    <div className="site-layout">
      <SiteHeader dashboard={activePage === 'dashboard'} />
      <div className="site-layout-content">{children}</div>
      <SiteFooter />
    </div>
  )
}
