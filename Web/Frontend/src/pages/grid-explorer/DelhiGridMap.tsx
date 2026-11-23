import { useState, type MouseEvent } from 'react'
import { DELHI_GRID_REGIONS, type GridRegionPartition, type UtilitySeriesKey } from './delhiGridTopology'

type ForecastRowLike = Record<string, unknown> & {
  timestamp?: string
}

type DelhiGridMapProps = {
  selectedRegionId: UtilitySeriesKey
  onSelectRegion: (id: UtilitySeriesKey) => void
  latestForecastRow?: ForecastRowLike | null
  showSubstations?: boolean
  showCorridors?: boolean
  showLandmarks?: boolean
}

type TooltipState = {
  region: GridRegionPartition
  x: number
  y: number
} | null

function formatMw(val: unknown): string {
  if (typeof val !== 'number' || Number.isNaN(val)) return '—'
  return `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(val)} MW`
}

export function DelhiGridMap({
  selectedRegionId,
  onSelectRegion,
  latestForecastRow,
  showSubstations = true,
  showCorridors = true,
  showLandmarks = true,
}: DelhiGridMapProps) {
  const [hoveredId, setHoveredId] = useState<UtilitySeriesKey | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState>(null)
  const [zoom, setZoom] = useState(1)

  const handleMouseMove = (event: MouseEvent<SVGElement>, region: GridRegionPartition) => {
    const bounds = event.currentTarget.ownerSVGElement?.getBoundingClientRect()
    if (!bounds) return
    setHoveredId(region.id)
    setTooltip({
      region,
      x: event.clientX - bounds.left + 14,
      y: event.clientY - bounds.top + 14,
    })
  }

  const handleMouseLeave = () => {
    setHoveredId(null)
    setTooltip(null)
  }

  return (
    <div style={{ position: 'relative', width: '100%', borderRadius: 20, overflow: 'hidden' }}>
      <div className="grid-map-controls" aria-label="Map zoom controls">
        <button type="button" onClick={() => setZoom((value) => Math.min(1.35, value + 0.15))} aria-label="Zoom in">+</button>
        <button type="button" onClick={() => setZoom((value) => Math.max(0.85, value - 0.15))} aria-label="Zoom out">−</button>
        <button type="button" onClick={() => setZoom(1)} aria-label="Reset map">↺</button>
      </div>
      <svg
        viewBox="0 0 800 800"
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label="Interactive Delhi SLDC and DTL utility region map"
        onMouseLeave={handleMouseLeave}
      >
        <g style={{ transform: `scale(${zoom})`, transformOrigin: '400px 400px', transition: 'transform 220ms ease' }}>
        <defs>
          <pattern id="gridMinor" width="32" height="32" patternUnits="userSpaceOnUse">
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="rgba(15, 23, 42, 0.06)"
              strokeWidth="1"
            />
          </pattern>
        </defs>

        <rect width="800" height="800" fill="url(#gridMinor)" />

        {/* Recognizable NCT Delhi outline */}
        <path
          d="M 252,82 C 330,68 420,74 468,96 C 512,116 532,154 548,198 C 562,236 610,268 640,315 C 676,372 686,433 672,498 C 658,562 618,635 558,690 C 494,748 402,765 326,733 C 246,700 178,661 126,594 C 87,544 92,482 118,421 C 143,361 145,301 176,246 C 202,198 218,137 252,82 Z"
          fill="rgba(255, 255, 255, 0.75)"
          stroke="#0f172a"
          strokeWidth="2.5"
        />

        {showLandmarks && (
          <g className="grid-map-geography">
            {/* Yamuna River */}
            <path d="M 522,112 C 508,190 520,244 554,292 C 576,324 558,378 538,430 C 514,492 532,552 572,635" fill="none" stroke="#60a5fa" strokeWidth="15" strokeOpacity="0.42" />
            <path d="M 522,112 C 508,190 520,244 554,292 C 576,324 558,378 538,430 C 514,492 532,552 572,635" fill="none" stroke="#bfdbfe" strokeWidth="2" strokeDasharray="5 7" />

            {/* Outer / inner Ring Road cues */}
            <path d="M 205,235 C 300,150 445,150 548,250 C 632,332 624,520 536,625 C 438,730 278,664 190,554 C 110,454 121,323 205,235 Z" fill="none" stroke="#94a3b8" strokeWidth="7" strokeOpacity="0.38" />
            <path d="M 205,235 C 300,150 445,150 548,250 C 632,332 624,520 536,625 C 438,730 278,664 190,554 C 110,454 121,323 205,235 Z" fill="none" stroke="#ffffff" strokeWidth="2" strokeDasharray="12 8" />
            <path d="M 270,300 C 354,254 447,278 497,351 C 548,425 508,540 426,580 C 338,622 250,570 224,488 C 198,408 214,330 270,300 Z" fill="none" stroke="#94a3b8" strokeWidth="5" strokeOpacity="0.5" />

            {/* Major Delhi landmarks */}
            <g transform="translate(445 407)">
              <circle r="6" fill="#ffffff" stroke="#b45309" strokeWidth="2" />
              <text x="10" y="4" fontSize="11" fontWeight="800" fill="#334155">Connaught Place</text>
            </g>
            <g transform="translate(490 340)">
              <circle r="5" fill="#ffffff" stroke="#dc2626" strokeWidth="2" />
              <text x="9" y="4" fontSize="10.5" fontWeight="800" fill="#334155">Red Fort</text>
            </g>
            <g transform="translate(400 650)">
              <circle r="5" fill="#ffffff" stroke="#2563eb" strokeWidth="2" />
              <text x="9" y="4" fontSize="10.5" fontWeight="800" fill="#334155">IGI Region</text>
            </g>
            <g transform="translate(352 220)">
              <circle r="5" fill="#ffffff" stroke="#0284c7" strokeWidth="2" />
              <text x="9" y="4" fontSize="10.5" fontWeight="800" fill="#334155">Rohini</text>
            </g>
          </g>
        )}

        {/* North Compass Marker (matches DTL map top-right orientation) */}
        <g transform="translate(720, 82)">
          <circle cx="0" cy="0" r="24" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1.5" />
          <polygon points="0,-16 6,4 0,0 -6,4" fill="#0f172a" />
          <text x="0" y="16" textAnchor="middle" fontSize="11" fontWeight="700" fill="#0f172a">
            N
          </text>
        </g>

        {/* Partitioned Project Regions + Hover Inner Parts */}
        {DELHI_GRID_REGIONS.map((region) => {
          const isHovered = hoveredId === region.id
          const isSelected = selectedRegionId === region.id
          const showInnerParts = isHovered || isSelected
          const dimmed = hoveredId !== null && !isHovered

          const isRailLine = region.id === 'railways_mw'

          return (
            <g
              key={region.id}
              style={{
                opacity: dimmed ? 0.42 : 1,
                transition: 'opacity 180ms ease, transform 180ms ease',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => handleMouseMove(e, region)}
              onMouseMove={(e) => handleMouseMove(e, region)}
              onClick={() => onSelectRegion(region.id)}
            >
              {isRailLine ? (
                <polyline
                  points={region.innerCorridors[0].points}
                  fill="none"
                  stroke={region.accent}
                  strokeWidth={showInnerParts ? 6 : 3.5}
                  strokeDasharray="8 5"
                  strokeLinecap="round"
                />
              ) : (
                <path
                  d={region.polygonPath}
                  fill={showInnerParts ? region.hoverFill : region.fill}
                  stroke={showInnerParts ? region.accent : '#334155'}
                  strokeWidth={isHovered ? 3 : isSelected ? 2.5 : 1.5}
                />
              )}

              {/* Region Code & Share Label */}
              <g transform={`translate(${region.labelPos.x}, ${region.labelPos.y})`}>
                <rect
                  x="-42"
                  y="-15"
                  width="84"
                  height="28"
                  rx="8"
                  fill={showInnerParts ? region.accent : 'rgba(15, 23, 42, 0.82)'}
                />
                <text
                  x="0"
                  y="3"
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="700"
                  fill="#ffffff"
                >
                  {region.code} · {region.sharePct}
                </text>
              </g>

              {/* Inner Parts: Revealed / Emphasized on Hover or Selection */}
              <g
                style={{
                  opacity: showInnerParts ? 1 : 0.28,
                  transition: 'opacity 180ms ease',
                  pointerEvents: 'none',
                }}
              >
                {showCorridors && region.innerCorridors.map((corr) => (
                  <polyline
                    key={corr.id}
                    points={corr.points}
                    fill="none"
                    stroke={region.accent}
                    strokeWidth={showInnerParts ? 3 : 1.5}
                    strokeDasharray={corr.voltage === '400 kV' ? undefined : '5 3'}
                  />
                ))}

                {showSubstations && region.innerSubstations.map((sub) => (
                  <g key={sub.id} transform={`translate(${sub.x}, ${sub.y})`}>
                    <polygon
                      points="0,-7 7,6 -7,6"
                      fill="#ffffff"
                      stroke={region.accent}
                      strokeWidth="2.2"
                    />
                    {showInnerParts && (
                      <text
                        x="10"
                        y="4"
                        fontSize="10.5"
                        fontWeight="700"
                        fill="#0f172a"
                      >
                        {sub.name}
                      </text>
                    )}
                  </g>
                ))}
              </g>
            </g>
          )
        })}
        </g>
      </svg>

      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: Math.min(tooltip.x, 420),
            top: Math.min(tooltip.y, 520),
            pointerEvents: 'none',
            background: 'rgba(10, 20, 42, 0.92)',
            color: '#f8fafc',
            padding: '10px 12px',
            borderRadius: 12,
            fontSize: 12,
            lineHeight: 1.45,
            boxShadow: '0 10px 24px rgba(0, 0, 0, 0.28)',
            zIndex: 10,
            maxWidth: 260,
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 2 }}>
            {tooltip.region.code} — {tooltip.region.name}
          </div>
          <div style={{ color: '#93c5fd', marginBottom: 4 }}>
            {tooltip.region.zoneLabel} ({tooltip.region.sharePct})
          </div>
          <div>
            Forecast P50:{' '}
            <strong>{formatMw(latestForecastRow?.[tooltip.region.id])}</strong>
          </div>
          <div>Peak Window: {tooltip.region.peakWindow}</div>
          <div>Inner Substations: {tooltip.region.innerSubstations.length} nodes</div>
        </div>
      )}
    </div>
  )
}