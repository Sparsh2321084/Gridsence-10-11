import { useState } from 'react'
import { BatteryCharging, BusFront, Gauge, ShieldAlert } from 'lucide-react'
import { apiUrl } from '../../../../lib/api'
import { DashboardCard } from './DashboardCard'
import type { AssetSimulationResult, ForecastResponse, ForecastTarget, SimulatorProfile } from '../types'

type Props = {
  data: ForecastResponse
  target: ForecastTarget
}

type FormValues = {
  corridorCapacity: string
  bessPower: string
  bessEnergy: string
  bessMinSoc: string
  bessInitialSoc: string
  bessMaxSoc: string
  bessEfficiency: string
  evBusCount: string
  evChargerKw: string
  evTargetEnergy: string
  drThreshold: string
  drEnrolled: string
  drCurtailable: string
  drDuration: string
}

function defaultForm(data: ForecastResponse, target: ForecastTarget): FormValues {
  const defaults = data.asset_simulations.defaults
  const bess = defaults.bess
  const ev = defaults.ev_fleet
  const dr = defaults.demand_response
  return {
    corridorCapacity: String(defaults.corridor_limits_mw[target]),
    bessPower: String(bess.power_mw),
    bessEnergy: String(bess.energy_mwh),
    bessMinSoc: String(bess.min_soc_pct),
    bessInitialSoc: String(bess.initial_soc_pct),
    bessMaxSoc: String(bess.max_soc_pct),
    bessEfficiency: String(bess.round_trip_efficiency),
    evBusCount: String(ev.bus_count),
    evChargerKw: String(ev.charger_kw_per_bus),
    evTargetEnergy: String(ev.target_energy_mwh),
    drThreshold: String(dr.trigger_threshold_mw_by_target[target] ?? ''),
    drEnrolled: String(dr.enrolled_capacity_mw),
    drCurtailable: String(dr.curtailable_fraction),
    drDuration: String(dr.event_duration_hours),
  }
}

function readNumber(value: string, label: string, allowBlank = false): number | undefined {
  if (allowBlank && value.trim() === '') return undefined
  const number = Number(value)
  if (!Number.isFinite(number)) throw new Error(`${label} must be a finite number`)
  return number
}

function NumberField({
  label,
  value,
  onChange,
  min = 0,
  max,
  step = 'any',
  suffix,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  min?: number
  max?: number
  step?: string
  suffix?: string
}) {
  return (
    <label className="simulator-field">
      <span>{label}{suffix ? ` (${suffix})` : ''}</span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}

function ProfileFields({
  values,
  update,
}: {
  values: FormValues
  update: (key: keyof FormValues, value: string) => void
}) {
  return (
    <details className="simulator-controls">
      <summary>Edit simulator parameters</summary>
      <div className="simulator-field-grid">
        <NumberField label="Nominal corridor limit" suffix="MW" value={values.corridorCapacity} onChange={(value) => update('corridorCapacity', value)} />
        <NumberField label="BESS power" suffix="MW" value={values.bessPower} onChange={(value) => update('bessPower', value)} />
        <NumberField label="BESS energy" suffix="MWh" value={values.bessEnergy} onChange={(value) => update('bessEnergy', value)} />
        <NumberField label="Minimum SOC" suffix="%" min={0} max={100} value={values.bessMinSoc} onChange={(value) => update('bessMinSoc', value)} />
        <NumberField label="Initial SOC" suffix="%" min={0} max={100} value={values.bessInitialSoc} onChange={(value) => update('bessInitialSoc', value)} />
        <NumberField label="Maximum SOC" suffix="%" min={0} max={100} value={values.bessMaxSoc} onChange={(value) => update('bessMaxSoc', value)} />
        <NumberField label="Round-trip efficiency" min={0.01} max={1} step="0.01" value={values.bessEfficiency} onChange={(value) => update('bessEfficiency', value)} />
        <NumberField label="E-bus fleet" value={values.evBusCount} onChange={(value) => update('evBusCount', value)} />
        <NumberField label="Charger per bus" suffix="kW" value={values.evChargerKw} onChange={(value) => update('evChargerKw', value)} />
        <NumberField label="EV target energy" suffix="MWh" value={values.evTargetEnergy} onChange={(value) => update('evTargetEnergy', value)} />
        <NumberField label="DR P95 trigger" suffix="MW" value={values.drThreshold} onChange={(value) => update('drThreshold', value)} />
        <NumberField label="Enrolled HVAC capacity" suffix="MW" value={values.drEnrolled} onChange={(value) => update('drEnrolled', value)} />
        <NumberField label="Curtailable fraction" min={0} max={1} step="0.01" value={values.drCurtailable} onChange={(value) => update('drCurtailable', value)} />
        <NumberField label="DR event duration" suffix="hours" min={0.25} step="0.25" value={values.drDuration} onChange={(value) => update('drDuration', value)} />
      </div>
    </details>
  )
}

function ProfileValue(profile: SimulatorProfile, key: keyof SimulatorProfile, fallback: number) {
  const value = profile[key]
  return typeof value === 'number' ? value : fallback
}

export function AssetSimulatorsBlock({ data, target }: Props) {
  const [values, setValues] = useState(() => defaultForm(data, target))
  const [result, setResult] = useState<AssetSimulationResult | null>(
    () => data.asset_simulations.target === target ? data.asset_simulations : null,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const update = (key: keyof FormValues, value: string) => {
    setValues((current) => ({ ...current, [key]: value }))
  }

  const runSimulators = async () => {
    setLoading(true)
    setError('')
    try {
      const request = {
        target,
        corridor_capacity_mw: readNumber(values.corridorCapacity, 'Corridor limit'),
        bess: {
          power_mw: readNumber(values.bessPower, 'BESS power'),
          energy_mwh: readNumber(values.bessEnergy, 'BESS energy'),
          min_soc_pct: readNumber(values.bessMinSoc, 'BESS minimum SOC'),
          initial_soc_pct: readNumber(values.bessInitialSoc, 'BESS initial SOC'),
          max_soc_pct: readNumber(values.bessMaxSoc, 'BESS maximum SOC'),
          round_trip_efficiency: readNumber(values.bessEfficiency, 'BESS efficiency'),
        },
        ev_fleet: {
          bus_count: readNumber(values.evBusCount, 'E-bus fleet'),
          charger_kw_per_bus: readNumber(values.evChargerKw, 'Charger rating'),
          target_energy_mwh: readNumber(values.evTargetEnergy, 'EV target energy'),
        },
        demand_response: {
          threshold_mw: readNumber(values.drThreshold, 'DR trigger threshold', true),
          enrolled_capacity_mw: readNumber(values.drEnrolled, 'Enrolled HVAC capacity'),
          curtailable_fraction: readNumber(values.drCurtailable, 'Curtailable fraction'),
          event_duration_hours: readNumber(values.drDuration, 'DR event duration'),
        },
      }
      const response = await fetch(apiUrl('/api/v1/simulate-assets'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
      const payload: unknown = await response.json()
      if (!response.ok) {
        const detail = payload && typeof payload === 'object' && 'detail' in payload
          ? String(payload.detail)
          : `Simulator API returned ${response.status}`
        throw new Error(detail)
      }
      if (
        !payload
        || typeof payload !== 'object'
        || !('simulations' in payload)
        || !payload.simulations
        || typeof payload.simulations !== 'object'
        || !('corridor' in payload.simulations)
        || !('bess' in payload.simulations)
        || !('ev_fleet' in payload.simulations)
        || !('demand_response' in payload.simulations)
      ) {
        throw new Error('Simulator API returned an incomplete response')
      }
      setResult(payload.simulations as AssetSimulationResult)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to run asset simulators')
    } finally {
      setLoading(false)
    }
  }

  const corridor = result?.corridor
  const bess = result?.bess
  const evFleet = result?.ev_fleet
  const demandResponse = result?.demand_response
  const activeBess = bess?.blocks.filter((block) => block.bess_mw !== 0) ?? []
  const activeEvBlocks = evFleet?.blocks.filter((block) => block.charging_mw > 0) ?? []

  return (
    <>
      <div className="asset-simulator-toolbar">
        <span className="data-connection-badge">Configurable Simulator · forecast inputs only</span>
        <button type="button" className="button button--outline" onClick={() => void runSimulators()} disabled={loading}>
          {loading ? 'Simulating…' : 'Run simulators'}
        </button>
      </div>
      <ProfileFields values={values} update={update} />
      {error && <p className="simulator-error" role="alert">{error}</p>}
      <div className="dashboard-block-grid dashboard-block-grid--resources simulator-grid">
        <DashboardCard title="Thermal line & N-1 corridor stress" icon={ShieldAlert} className="dashboard-card--6">
          <span className="data-connection-badge">Configurable Simulator</span>
          {corridor ? (
            <>
              <strong className="simulator-primary-value">{corridor.peak_status.replaceAll('_', ' ')}</strong>
              <p>Peak P95 utilization: {corridor.peak_utilization_pct.toFixed(1)}% of derated capacity</p>
              <p>{corridor.safe_maintenance_blocks.length} safe overnight maintenance blocks (&lt;55% utilization)</p>
              <small>{corridor.assumption}</small>
            </>
          ) : <p>Run the simulator for the selected area to calculate P95 stress and maintenance blocks.</p>}
        </DashboardCard>

        <DashboardCard title="BESS peak-shaving schedule" icon={BatteryCharging} className="dashboard-card--6">
          <span className="data-connection-badge">Configurable Simulator</span>
          {bess ? (
            <>
              <strong className="simulator-primary-value">{bess.peak_shaved_mw.toFixed(1)} MW peak shave</strong>
              <p>Charged {bess.energy_charged_mwh.toFixed(1)} MWh · discharged {bess.energy_discharged_mwh.toFixed(1)} MWh · ending SOC {bess.ending_soc_pct.toFixed(1)}%</p>
              <details className="simulator-schedule">
                <summary>{activeBess.length} non-zero schedule blocks</summary>
                {activeBess.map((block) => (
                  <p key={block.timestamp}>
                    {new Date(block.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                    {' · '}{block.bess_mw > 0 ? `Discharge ${block.bess_mw.toFixed(1)} MW` : `Charge ${Math.abs(block.bess_mw).toFixed(1)} MW`}
                    {' · '}SOC {block.soc_pct.toFixed(1)}%
                  </p>
                ))}
              </details>
              <small>{bess.assumption}</small>
            </>
          ) : <p>Run the simulator to calculate the configured 20 MW / 40 MWh profile.</p>}
        </DashboardCard>

        <DashboardCard title="EV fleet valley filling" icon={BusFront} className="dashboard-card--6">
          <span className="data-connection-badge">Configurable Simulator</span>
          {evFleet ? (
            <>
              <strong className="simulator-primary-value">{evFleet.scheduled_energy_mwh.toFixed(1)} / {ProfileValue(evFleet.profile, 'target_energy_mwh', 65).toFixed(1)} MWh scheduled</strong>
              <p>{evFleet.unallocated_energy_mwh.toFixed(1)} MWh unallocated · {ProfileValue(evFleet.profile, 'max_charger_mw', 90).toFixed(1)} MW charger cap</p>
              <details className="simulator-schedule">
                <summary>{activeEvBlocks.length} active overnight blocks</summary>
                {activeEvBlocks.map((block) => (
                  <p key={block.timestamp}>
                    {new Date(block.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                    {' · '}{block.charging_mw.toFixed(1)} MW · {block.energy_mwh.toFixed(2)} MWh
                  </p>
                ))}
              </details>
              <small>{evFleet.assumption}</small>
            </>
          ) : <p>Run the simulator to allocate the configurable fleet across overnight valley blocks.</p>}
        </DashboardCard>

        <DashboardCard title="VPP & demand response" icon={Gauge} className="dashboard-card--6">
          <span className="data-connection-badge">Configurable Simulator</span>
          {demandResponse ? (
            <>
              <strong className="simulator-primary-value">
                {demandResponse.configured ? (demandResponse.triggered ? 'TRIGGERED' : 'Not triggered') : 'Threshold needed'}
              </strong>
              {demandResponse.triggered && demandResponse.precooling_window && (
                <p>Pre-cooling: {new Date(demandResponse.precooling_window.start).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  {' – '}{new Date(demandResponse.precooling_window.end).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</p>
              )}
              <p>{demandResponse.mw_shaved.toFixed(1)} MW simulated shave · {demandResponse.active_curtailment_blocks.length} active blocks</p>
              {demandResponse.reason && <p>{demandResponse.reason}</p>}
              <small>{demandResponse.assumption}</small>
            </>
          ) : <p>Run the simulator to evaluate the selected area’s P95 trigger threshold.</p>}
        </DashboardCard>
      </div>
      <p className="dashboard-card-caption simulator-disclaimer">
        Simulations are editable planning examples only. They do not use live SCADA, asset SOC, vehicle availability, customer enrollment telemetry, or issue control/dispatch commands.
      </p>
    </>
  )
}
