import { Zap } from 'lucide-react'

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <a className={`brand${compact ? ' brand--compact' : ''}`} href="/" aria-label="GridSense home">
      <Zap aria-hidden="true" fill="currentColor" strokeWidth={1.5} />
      <span>Grid<span>Sense</span></span>
    </a>
  )
}
