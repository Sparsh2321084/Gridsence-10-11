export type UtilitySeriesKey =
  | 'brpl_mw'
  | 'tpddl_mw'
  | 'bypl_mw'
  | 'ndmc_mw'
  | 'mes_mw'
  | 'railways_mw'

export type InnerSubstation = {
  id: string
  name: string
  voltage: '400/220 kV' | '220/66 kV' | '220/33 kV' | 'Generation / GIS'
  x: number
  y: number
}

export type InnerCorridor = {
  id: string
  label: string
  voltage: '400 kV' | '220 kV' | '25 kV Traction'
  points: string // SVG polyline points within 0..800 x 0..820
}

export type GridRegionPartition = {
  id: UtilitySeriesKey
  code: 'BRPL' | 'TPDDL' | 'BYPL' | 'NDMC' | 'MES' | 'RAILWAYS'
  name: string
  zoneLabel: string
  archetype: string
  sharePct: string
  peakWindow: string
  accent: string
  fill: string
  hoverFill: string
  polygonPath: string
  labelPos: { x: number; y: number }
  innerSubstations: InnerSubstation[]
  innerCorridors: InnerCorridor[]
}

export const DELHI_GRID_REGIONS: GridRegionPartition[] = [
  {
    id: 'tpddl_mw',
    code: 'TPDDL',
    name: 'Tata Power Delhi Distribution',
    zoneLabel: 'North & North-West Delhi',
    archetype: 'Residential + Industrial (Bawana / Narela)',
    sharePct: '30.59%',
    peakWindow: '14:30–16:30 & 22:30 IST',
    accent: '#0284c7',
    fill: 'rgba(14, 165, 233, 0.16)',
    hoverFill: 'rgba(14, 165, 233, 0.34)',
    polygonPath:
      'M 255,115 L 445,105 L 515,185 L 485,335 L 395,385 L 250,365 L 185,265 Z',
    labelPos: { x: 345, y: 215 },
    innerSubstations: [
      { id: 'bawana', name: 'Bawana 400/220kV & CCGT', voltage: '400/220 kV', x: 245, y: 165 },
      { id: 'narela', name: 'Narela 220kV', voltage: '220/66 kV', x: 345, y: 138 },
      { id: 'rohini', name: 'Rohini & DSIIDC', voltage: '220/66 kV', x: 315, y: 248 },
      { id: 'shalimar', name: 'Shalimar Bagh / Gopalpur', voltage: '220/66 kV', x: 435, y: 235 },
      { id: 'wazirpur', name: 'Wazirpur / Subzi Mandi', voltage: '220/33 kV', x: 375, y: 325 },
    ],
    innerCorridors: [
      { id: 'tp-1', label: 'Bawana–Rohini 220kV', voltage: '220 kV', points: '245,165 315,248 375,325' },
      { id: 'tp-2', label: 'Narela–Gopalpur 220kV', voltage: '220 kV', points: '345,138 435,235' },
    ],
  },
  {
    id: 'bypl_mw',
    code: 'BYPL',
    name: 'BSES Yamuna Power Limited',
    zoneLabel: 'Central & East Delhi',
    archetype: 'Dense Residential + Evening AC Surge',
    sharePct: '21.84%',
    peakWindow: '22:30–00:30 IST',
    accent: '#0d9488',
    fill: 'rgba(20, 184, 166, 0.16)',
    hoverFill: 'rgba(20, 184, 166, 0.34)',
    polygonPath:
      'M 485,335 L 555,275 L 675,345 L 655,515 L 525,510 L 465,435 Z',
    labelPos: { x: 565, y: 395 },
    innerSubstations: [
      { id: 'kashmiri', name: 'Kashmiri Gate / Geeta Colony', voltage: '220/33 kV', x: 515, y: 345 },
      { id: 'patparganj', name: 'Patparganj 220kV', voltage: '220/66 kV', x: 615, y: 385 },
      { id: 'gazipur', name: 'Gazipur / Preet Vihar', voltage: '220/66 kV', x: 635, y: 455 },
      { id: 'pragati', name: 'IP / Pragati / Rajghat', voltage: 'Generation / GIS', x: 495, y: 435 },
    ],
    innerCorridors: [
      { id: 'by-1', label: 'Patparganj–Gazipur 220kV', voltage: '220 kV', points: '615,385 635,455 495,435' },
      { id: 'by-2', label: 'Geeta Colony–Pragati', voltage: '220 kV', points: '515,345 495,435' },
    ],
  },
  {
    id: 'ndmc_mw',
    code: 'NDMC',
    name: 'New Delhi Municipal Council',
    zoneLabel: 'Lutyens & Administrative Core',
    archetype: 'Commercial & Govt Offices (Daytime Peak)',
    sharePct: '3.92%',
    peakWindow: '12:45–16:00 IST',
    accent: '#d97706',
    fill: 'rgba(245, 158, 11, 0.22)',
    hoverFill: 'rgba(245, 158, 11, 0.42)',
    polygonPath:
      'M 395,385 L 465,375 L 475,455 L 405,465 Z',
    labelPos: { x: 435, y: 422 },
    innerSubstations: [
      { id: 'park-st', name: 'Park Street 220kV', voltage: '220/33 kV', x: 422, y: 402 },
      { id: 'electric-lane', name: 'Electric Lane / Vidyut Bhawan', voltage: '220/33 kV', x: 452, y: 435 },
    ],
    innerCorridors: [
      { id: 'nd-1', label: 'Park St–Electric Lane Feed', voltage: '220 kV', points: '422,402 452,435' },
    ],
  },
  {
    id: 'brpl_mw',
    code: 'BRPL',
    name: 'BSES Rajdhani Power Limited',
    zoneLabel: 'South & West Delhi',
    archetype: 'Residential Cooling + Mixed Commercial',
    sharePct: '42.50%',
    peakWindow: '15:15 & 22:30–00:30 IST',
    accent: '#2563eb',
    fill: 'rgba(37, 99, 235, 0.16)',
    hoverFill: 'rgba(37, 99, 235, 0.34)',
    polygonPath:
      'M 125,455 L 250,365 L 395,385 L 405,465 L 475,455 L 525,510 L 555,685 L 385,735 L 215,665 L 115,575 Z',
    labelPos: { x: 315, y: 565 },
    innerSubstations: [
      { id: 'mundka', name: 'Mundka 400/220kV', voltage: '400/220 kV', x: 185, y: 445 },
      { id: 'dwarka', name: 'Dwarka / PPK I–III', voltage: '220/66 kV', x: 175, y: 565 },
      { id: 'rk-puram', name: 'RK Puram / Ridge Valley', voltage: '220/66 kV', x: 365, y: 495 },
      { id: 'mehrauli', name: 'Mehrauli / Vasant Kunj', voltage: '220/66 kV', x: 315, y: 615 },
      { id: 'okhla', name: 'Okhla / Sarita Vihar / Tughlakabad', voltage: '400/220 kV', x: 475, y: 615 },
    ],
    innerCorridors: [
      { id: 'br-1', label: 'Mundka–Dwarka–RK Puram 220kV', voltage: '220 kV', points: '185,445 175,565 365,495' },
      { id: 'br-2', label: 'RK Puram–Mehrauli–Okhla 220kV', voltage: '220 kV', points: '365,495 315,615 475,615' },
    ],
  },
  {
    id: 'mes_mw',
    code: 'MES',
    name: 'Military Engineer Services',
    zoneLabel: 'Delhi Cantonment Enclave',
    archetype: 'Institutional / Defense Schedule',
    sharePct: '0.72%',
    peakWindow: 'Institutional Daytime / Evening',
    accent: '#7c3aed',
    fill: 'rgba(124, 58, 237, 0.22)',
    hoverFill: 'rgba(124, 58, 237, 0.42)',
    polygonPath:
      'M 265,455 L 345,450 L 355,515 L 270,520 Z',
    labelPos: { x: 308, y: 486 },
    innerSubstations: [
      { id: 'cantt-gss', name: 'Delhi Cantt Bulk Drawal Node', voltage: '220/66 kV', x: 308, y: 486 },
    ],
    innerCorridors: [
      { id: 'mes-1', label: 'Cantt Feeder Tie', voltage: '220 kV', points: '270,486 345,486' },
    ],
  },
  {
    id: 'railways_mw',
    code: 'RAILWAYS',
    name: 'Northern Railway Traction',
    zoneLabel: '25 kV AC Rail Corridors',
    archetype: 'Timetable-Driven Electric Traction',
    sharePct: '0.43%',
    peakWindow: 'Train Schedule Bursts',
    accent: '#dc2626',
    fill: 'rgba(220, 38, 38, 0.16)',
    hoverFill: 'rgba(220, 38, 38, 0.34)',
    polygonPath:
      'M 165,205 L 635,595',
    labelPos: { x: 465, y: 525 },
    innerSubstations: [
      { id: 'traction-n', name: 'North/West Traction Feed', voltage: '220/33 kV', x: 265, y: 275 },
      { id: 'traction-s', name: 'South/Central Traction Feed', voltage: '220/33 kV', x: 485, y: 495 },
    ],
    innerCorridors: [
      { id: 'rl-1', label: 'Delhi Suburban 25kV Rail Trunk', voltage: '25 kV Traction', points: '165,205 385,385 485,495 635,595' },
    ],
  },
]