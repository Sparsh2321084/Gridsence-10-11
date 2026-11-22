import type { ReactNode } from 'react'
import { SiteFooter } from './SiteFooter'
import { SiteHeader } from './SiteHeader'

export type ActivePage = 'home' | 'dashboard' | 'grid-explorer'

type SiteLayoutProps = {
  activePage: ActivePage
  children: ReactNode
}

export function SiteLayout({ activePage, children }: SiteLayoutProps) {
  return (
    <div className="site-layout">
      <SiteHeader activePage={activePage} />
      <div className="site-layout-content">{children}</div>
      <SiteFooter />
    </div>
  )
}