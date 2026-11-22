import { useEffect, useState, type CSSProperties, type MouseEvent } from 'react'
import {
  Activity,
  ArrowRight,
  Compass,
  Layers,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  Zap,
} from 'lucide-react'

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

type HeroTelemetry = {
  peakMw: string
  p95Mw: string
  peakTime: string
  modeLabel: string
  isLive: boolean
}

const FALLBACK_TELEMETRY: HeroTelemetry = {
  peakMw: '4,494.5 MW',
  p95Mw: '4,870.0 MW',
  peakTime: '03:00 pm IST',
  modeLabel: 'STALE Baseline',
  isLive: false,
}

const DOCK_ITEMS = [
  { label: 'Observed Grid Peak', value: '8,539.4 MW', sub: 'Delhi SLDC Archive (2019–2026)', icon: Zap },
  { label: 'Reconciled Hierarchy', value: '7 Entities', sub: '6 Utilities + Coherent City Total', icon: Layers },
  { label: 'Settlement Horizon', value: '96 Blocks', sub: '15-Min ABT / DSM Grid', icon: Activity },
]

const glassLightStyle: CSSProperties = {
  background: 'linear-gradient(145deg, rgba(255,255,255,0.88) 0%, rgba(241,247,255,0.65) 100%)',
  backdropFilter: 'blur(22px) saturate(185%)',
  WebkitBackdropFilter: 'blur(22px) saturate(185%)',
  border: '1.5px solid rgba(255,255,255,0.96)',
  boxShadow:
    '0 22px 44px -14px rgba(14, 39, 86, 0.16), 0 3px 0 rgba(208, 226, 250, 0.85), inset 0 1.5px 0 #ffffff',
}

export function HeroSection() {
  const [telemetry, setTelemetry] = useState<HeroTelemetry>(FALLBACK_TELEMETRY)
  const [tilt, setTilt] = useState({ rx: 4, ry: -7 })

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${API_BASE}/api/forecast`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((payload) => {
        if (!payload || !Array.isArray(payload.forecast) || payload.forecast.length === 0) return
        let peakRow = payload.forecast[0]
        for (const row of payload.forecast) {
          if (typeof row.delhi_total_mw === 'number' && row.delhi_total_mw > peakRow.delhi_total_mw) {
            peakRow = row
          }
        }
        const fmt = (n: number) =>
          `${new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 }).format(n)} MW`
        const mode = payload.data_freshness?.forecast_mode ?? 'STALE'
        setTelemetry({
          peakMw: fmt(peakRow.delhi_total_mw),
          p95Mw: fmt(peakRow.delhi_total_mw_p95 ?? peakRow.delhi_total_mw),
          peakTime: new Date(peakRow.timestamp).toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
            timeZone: 'Asia/Kolkata',
          }) + ' IST',
          modeLabel: mode === 'LIVE' ? 'Live SLDC Feed' : `${mode} Baseline`,
          isLive: mode === 'LIVE',
        })
      })
      .catch(() => {})

    return () => controller.abort()
  }, [])

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5
    const y = (e.clientY - r.top) / r.height - 0.5
    setTilt({ rx: Number((-y * 10).toFixed(2)), ry: Number((x * 12).toFixed(2)) })
  }

  return (
    <section
      style={{
        position: 'relative',
        minHeight: 'calc(100svh - 76px)',
        display: 'flex',
        alignItems: 'center',
        padding: '32px 0 36px',
      }}
      aria-labelledby="hero-title"
    >
      <div className="page-width" style={{ display: 'flex', flexDirection: 'column', gap: 36 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            alignItems: 'center',
            gap: 40,
          }}
        >
          {/* Left Copy */}
          <div>
            <div
              style={{
                ...glassLightStyle,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '7px 14px',
                borderRadius: 999,
                fontSize: '0.76rem',
                fontWeight: 700,
                color: '#154ec7',
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#10b981',
                  boxShadow: '0 0 0 4px rgba(16,185,129,0.22)',
                }}
              />
              Delhi SLDC · 15-Min Probabilistic Grid Intelligence
            </div>

            <h1
              id="hero-title"
              style={{
                margin: '16px 0 8px',
                fontSize: 'clamp(3.2rem, 6vw, 5.6rem)',
                lineHeight: 0.94,
                letterSpacing: '-0.05em',
                fontWeight: 800,
                color: '#0b1b36',
              }}
            >
              Grid<span style={{ color: '#1163eb' }}>Sense</span>
            </h1>

            <p
              style={{
                margin: '0 0 12px',
                fontSize: 'clamp(1.05rem, 1.6vw, 1.35rem)',
                fontWeight: 700,
                letterSpacing: '-0.025em',
                color: '#18325c',
              }}
            >
              Spatial Multi-Utility Forecasting &amp; Reserve Intelligence
            </p>

            <p
              style={{
                maxWidth: 520,
                margin: '0 0 24px',
                color: '#475f82',
                fontSize: '0.98rem',
                lineHeight: 1.65,
              }}
            >
              Coherently reconciled 24-hour load trajectories across Delhi&apos;s six distribution
              utilities—uniting cross-variable Transformer attention, physical-scale MinT
              reconciliation, causal drift calibration, and Adaptive Conformal Inference.
            </p>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              <a
                href="/dashboard"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 22px',
                  borderRadius: 16,
                  textDecoration: 'none',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  color: '#fff',
                  background: 'linear-gradient(180deg, #2777f8 0%, #0d50c7 100%)',
                  border: '1px solid rgba(255,255,255,0.32)',
                  boxShadow:
                    '0 16px 30px -8px rgba(17, 99, 235, 0.5), 0 3px 0 #08378c, inset 0 1.5px 0 rgba(255,255,255,0.45)',
                }}
              >
                Open Dashboard <ArrowRight size={17} />
              </a>

              <a
                href="/grid-explorer"
                style={{
                  ...glassLightStyle,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '12px 20px',
                  borderRadius: 16,
                  textDecoration: 'none',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  color: '#1163eb',
                }}
              >
                <Compass size={17} /> Grid Explorer
              </a>
            </div>
          </div>

          {/* Right 3D Glass Stage */}
          <div
            onMouseMove={onMove}
            onMouseLeave={() => setTilt({ rx: 4, ry: -7 })}
            style={{
              position: 'relative',
              display: 'grid',
              placeItems: 'center',
              padding: '24px 12px',
            }}
          >
            <img
              src="/delhi-grid.svg"
              alt="Delhi transmission and load profile illustration"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                borderRadius: 32,
                opacity: 0.45,
                pointerEvents: 'none',
              }}
            />

            <div
              style={{
                position: 'relative',
                width: '100%',
                maxWidth: 460,
                transformStyle: 'preserve-3d',
                transform: `perspective(1200px) rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
                transition: 'transform 0.22s ease-out',
              }}
            >
              {/* Floating Z-Layer Chip: Top Left */}
              <div
                style={{
                  ...glassLightStyle,
                  position: 'relative',
                  zIndex: 3,
                  width: 'fit-content',
                  marginBottom: -14,
                  marginLeft: -12,
                  padding: '9px 14px',
                  borderRadius: 16,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  transform: 'translateZ(36px)',
                }}
              >
                <span
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 10,
                    display: 'grid',
                    placeItems: 'center',
                    background: 'rgba(16,185,129,0.14)',
                    color: '#059669',
                  }}
                >
                  <TrendingDown size={16} />
                </span>
                <div>
                  <div style={{ fontSize: '0.66rem', fontWeight: 700, color: '#5b7396' }}>
                    2026 Citywide MAPE
                  </div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#0b1b36' }}>
                    2.856% (192.67 MW Peak MAE)
                  </div>
                </div>
              </div>

              {/* Main 3D Dark Glass Console */}
              <div
                style={{
                  position: 'relative',
                  zIndex: 2,
                  padding: 22,
                  borderRadius: 28,
                  color: '#f8fafc',
                  background:
                    'linear-gradient(145deg, rgba(16, 33, 68, 0.94) 0%, rgba(8, 19, 43, 0.88) 100%)',
                  backdropFilter: 'blur(24px)',
                  WebkitBackdropFilter: 'blur(24px)',
                  border: '1.5px solid rgba(255,255,255,0.25)',
                  boxShadow:
                    '0 36px 68px -16px rgba(4, 11, 28, 0.62), 0 7px 0 #153166, inset 0 1.5px 0 rgba(255,255,255,0.35)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                    marginBottom: 14,
                  }}
                >
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: '#93c5fd',
                    }}
                  >
                    <Sparkles size={14} /> iTransformer + MinT + ACI
                  </span>
                  <span
                    style={{
                      padding: '4px 10px',
                      borderRadius: 999,
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      background: telemetry.isLive
                        ? 'rgba(16,185,129,0.2)'
                        : 'rgba(251,191,36,0.16)',
                      color: telemetry.isLive ? '#6ee7b7' : '#fcd34d',
                      border: telemetry.isLive
                        ? '1px solid rgba(16,185,129,0.35)'
                        : '1px solid rgba(251,191,36,0.3)',
                    }}
                  >
                    {telemetry.modeLabel}
                  </span>
                </div>

                {/* Two Distinct Recessed Metric Pods */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 12,
                  }}
                >
                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: 18,
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      boxShadow: 'inset 0 2px 6px rgba(2,8,20,0.4)',
                    }}
                  >
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600 }}>
                      Expected Peak (P50)
                    </div>
                    <div
                      style={{
                        fontSize: '1.25rem',
                        fontWeight: 800,
                        margin: '3px 0',
                        letterSpacing: '-0.03em',
                        color: '#ffffff',
                      }}
                    >
                      {telemetry.peakMw}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 600 }}>
                      {telemetry.peakTime}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: 18,
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.12)',
                      boxShadow: 'inset 0 2px 6px rgba(2,8,20,0.4)',
                    }}
                  >
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600 }}>
                      ACI Ceiling (P95)
                    </div>
                    <div
                      style={{
                        fontSize: '1.25rem',
                        fontWeight: 800,
                        margin: '3px 0',
                        letterSpacing: '-0.03em',
                        color: '#ffffff',
                      }}
                    >
                      {telemetry.p95Mw}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 600 }}>
                      90% Target Band
                    </div>
                  </div>
                </div>

                <svg
                  viewBox="0 0 320 88"
                  style={{ display: 'block', width: '100%', height: 86, marginTop: 12 }}
                  role="img"
                  aria-label="96-block probabilistic load trajectory"
                >
                  <defs>
                    <linearGradient id="glassCurve3d" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.45" />
                      <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.04" />
                    </linearGradient>
                  </defs>
                  <path
                    d="M8,62 C48,68 78,56 112,38 C148,18 178,22 214,32 C248,40 278,14 312,22 L312,48 C278,40 248,60 214,54 C178,46 148,44 112,62 C78,76 48,80 8,76 Z"
                    fill="url(#glassCurve3d)"
                  />
                  <path
                    d="M8,70 C48,74 78,66 112,50 C148,30 178,34 214,43 C248,50 278,26 312,35"
                    fill="none"
                    stroke="#60a5fa"
                    strokeWidth="2.8"
                    strokeLinecap="round"
                  />
                  <circle cx="288" cy="26" r="5" fill="#34d399" />
                  <circle cx="288" cy="26" r="10" fill="#34d399" fillOpacity="0.24" />
                </svg>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '0.68rem',
                    color: '#94a3b8',
                    fontWeight: 600,
                  }}
                >
                  <span>00:00</span>
                  <span>Midday PV Dip</span>
                  <span>Evening AC Peak</span>
                  <span>23:45</span>
                </div>
              </div>

              {/* Floating Z-Layer Chip: Bottom Right */}
              <div
                style={{
                  ...glassLightStyle,
                  position: 'relative',
                  zIndex: 3,
                  width: 'fit-content',
                  marginTop: -14,
                  marginLeft: 'auto',
                  marginRight: -10,
                  padding: '9px 14px',
                  borderRadius: 16,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  transform: 'translateZ(36px)',
                }}
              >
                <span
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: 10,
                    display: 'grid',
                    placeItems: 'center',
                    background: 'rgba(17,99,235,0.12)',
                    color: '#1163eb',
                  }}
                >
                  <ShieldCheck size={16} />
                </span>
                <div>
                  <div style={{ fontSize: '0.66rem', fontWeight: 700, color: '#5b7396' }}>
                    ACI Reliability (7 Series)
                  </div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#0b1b36' }}>
                    87.64%–88.44% Coverage
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom 3D Frosted Telemetry Dock */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 14,
          }}
        >
          {DOCK_ITEMS.map(({ label, value, sub, icon: Icon }) => (
            <div
              key={label}
              style={{
                ...glassLightStyle,
                padding: '15px 18px',
                borderRadius: 22,
                display: 'flex',
                alignItems: 'center',
                gap: 14,
              }}
            >
              <span
                style={{
                  width: 38,
                  height: 38,
                  minWidth: 38,
                  borderRadius: 12,
                  display: 'grid',
                  placeItems: 'center',
                  background: 'linear-gradient(180deg, #ffffff 0%, #dceaff 100%)',
                  border: '1px solid #ffffff',
                  color: '#1163eb',
                  boxShadow: '0 8px 14px -4px rgba(17,99,235,0.2)',
                }}
              >
                <Icon size={17} />
              </span>
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#5b7396' }}>{label}</div>
                <div
                  style={{
                    fontSize: '1.18rem',
                    fontWeight: 800,
                    color: '#0b1b36',
                    letterSpacing: '-0.03em',
                  }}
                >
                  {value}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#647b9c' }}>{sub}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default HeroSection