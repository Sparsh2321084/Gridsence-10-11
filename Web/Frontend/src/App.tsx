import './App.css'
import { SiteLayout } from './components/layout/SiteLayout'
import { DashboardPage } from './pages/dashboard/DashboardPage'
import { HomePage } from './pages/home/HomePage'

export default function App() {
  const isDashboard = window.location.pathname.replace(/\/$/, '') === '/dashboard'

  return (
    <SiteLayout activePage={isDashboard ? 'dashboard' : 'home'}>
      {isDashboard ? <DashboardPage /> : <HomePage />}
    </SiteLayout>
  )
}
