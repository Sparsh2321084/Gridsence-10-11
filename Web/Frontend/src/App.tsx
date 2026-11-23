import './App.css'
import { SiteLayout } from './components/layout/SiteLayout'
import { DashboardPage } from './pages/dashboard/DashboardPage'
import { HomePage } from './pages/home/HomePage'
import { GridExplorerPage } from './pages/grid-explorer/GridExplorerPage'

export default function App() {
  const path = window.location.pathname.replace(/\/$/, '')
  const activePage =
    path === '/dashboard'
      ? 'dashboard'
      : path === '/grid-explorer'
        ? 'grid-explorer'
        : 'home'

  return (
    <SiteLayout activePage={activePage}>
      {activePage === 'dashboard' && <DashboardPage />}
      {activePage === 'grid-explorer' && <GridExplorerPage />}
      {activePage === 'home' && <HomePage />}
    </SiteLayout>
  )
}