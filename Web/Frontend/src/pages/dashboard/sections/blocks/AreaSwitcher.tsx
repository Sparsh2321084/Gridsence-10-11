import { utilityAreas } from '../types'
import type { UtilityArea } from '../types'

type AreaSwitcherProps = {
  selectedArea: UtilityArea | null
  onSelect: (area: UtilityArea | null) => void
}

export function AreaSwitcher({ selectedArea, onSelect }: AreaSwitcherProps) {
  return (
    <nav className="area-switcher" aria-label="Select dashboard area">
      <button
        type="button"
        className={!selectedArea ? 'active' : ''}
        aria-pressed={!selectedArea}
        onClick={() => onSelect(null)}
      >
        All Delhi
      </button>
      {utilityAreas.map((area) => (
        <button
          key={area.id}
          type="button"
          className={selectedArea?.id === area.id ? 'active' : ''}
          aria-pressed={selectedArea?.id === area.id}
          onClick={() => onSelect(area)}
        >
          {area.label}
        </button>
      ))}
    </nav>
  )
}
