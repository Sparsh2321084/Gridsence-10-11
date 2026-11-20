export const utilityAreas = [
  { id: 'brpl', label: 'BRPL', target: 'brpl_mw' },
  { id: 'tpddl', label: 'TPDDL', target: 'tpddl_mw' },
  { id: 'bypl', label: 'BYPL', target: 'bypl_mw' },
  { id: 'ndmc', label: 'NDMC', target: 'ndmc_mw' },
  { id: 'mes', label: 'MES', target: 'mes_mw' },
  { id: 'railways', label: 'Railways', target: 'railways_mw' },
] as const

export type UtilityArea = (typeof utilityAreas)[number]
export type ForecastTarget = 'delhi_total_mw' | UtilityArea['target']
export type ForecastMode = 'LIVE' | 'STALE' | 'REPLAYED' | 'UNAVAILABLE'
export type RampSeverity = 'NORMAL' | 'MODERATE' | 'SEVERE'

export type RampAssessment = {
  absolute_change_mw: number | null
  severity: RampSeverity | null
  p75_mw: number
  p95_mw: number
}

export type PpaDispatch = {
  required_reserve_mw: number
  contracted_ppa_mw: number | null
  net_position_mw: number | null
  iex_dam_action: 'BUY' | 'SELL' | 'BALANCED' | null
  rtm_reserve_buffer_mw: number | null
}

export type SimulatorProfile = {
  power_mw?: number
  energy_mwh?: number
  min_soc_pct?: number
  max_soc_pct?: number
  initial_soc_pct?: number
  round_trip_efficiency?: number
  bus_count?: number
  charger_kw_per_bus?: number
  max_charger_mw?: number
  target_energy_mwh?: number
  nominal_limit_mw?: number
  threshold_mw?: number | null
  enrolled_capacity_mw?: number
  curtailable_fraction?: number
  max_shave_mw?: number
  lead_time_hours?: number
  event_duration_hours?: number
  charge_window?: { start: string; end: string }
  discharge_windows?: Array<{ start: string; end: string }>
  charging_window?: { start: string; end: string }
  valley_window?: { start: string; end: string }
}

export type CorridorSimulatorBlock = {
  timestamp: string
  p95_mw: number
  temperature_c: number
  nominal_limit_mw: number
  derated_limit_mw: number
  utilization_pct: number
  status: 'NORMAL' | 'ELEVATED_SAG' | 'N1_THERMAL_RISK'
  safe_maintenance_window: boolean
}

export type AssetSimulationResult = {
  mode: 'CONFIGURABLE_SIMULATOR'
  operational_dispatch: false
  target: ForecastTarget
  data_source: string
  defaults: {
    corridor_limits_mw: Record<ForecastTarget, number>
    bess: SimulatorProfile
    ev_fleet: SimulatorProfile
    demand_response: SimulatorProfile & {
      trigger_threshold_mw_by_target: Partial<Record<ForecastTarget, number>>
    }
  }
  corridor: {
    profile: { nominal_limit_mw: number }
    blocks: CorridorSimulatorBlock[]
    peak_utilization_pct: number
    peak_status: CorridorSimulatorBlock['status']
    safe_maintenance_blocks: CorridorSimulatorBlock[]
    assumption: string
  }
  bess: {
    profile: SimulatorProfile
    blocks: Array<{
      timestamp: string
      load_p50_mw: number
      bess_mw: number
      soc_pct: number
      peak_shaved_mw: number
    }>
    energy_charged_mwh: number
    energy_discharged_mwh: number
    peak_shaved_mw: number
    ending_soc_pct: number
    assumption: string
  }
  ev_fleet: {
    profile: SimulatorProfile
    blocks: Array<{
      timestamp: string
      load_p50_mw: number
      charging_mw: number
      energy_mwh: number
      valley_window: boolean
    }>
    scheduled_energy_mwh: number
    unallocated_energy_mwh: number
    water_level_mw: number | null
    assumption: string
  }
  demand_response: {
    profile: SimulatorProfile
    configured: boolean
    triggered: boolean
    reason?: string
    peak_timestamp: string | null
    peak_p95_mw: number | null
    precooling_window: { start: string; end: string } | null
    active_curtailment_blocks: Array<{
      timestamp: string
      p95_mw: number
      mw_shaved: number
    }>
    mw_shaved: number
    total_shaved_energy_mwh?: number
    assumption: string
  }
}

export type DataFreshness = {
  latest_actual_timestamp: string | null
  lag_minutes: number | null
  forecast_mode: ForecastMode
  valid_blocks_percent: number
  filled_blocks: number
}

export type ForecastRow = {
  timestamp: string
  yesterday_actuals: Record<ForecastTarget, number | null>
  ramp_assessments: Record<ForecastTarget, RampAssessment>
  required_reserve_mw: Record<ForecastTarget, number>
  ppa_dispatch: PpaDispatch | null
  thermal_coal_burn: {
    energy_mwh: number
    estimated_coal_burn_tonnes: number
    thermal_mix_share: number
  }
  weather: {
    temperature_2m: number | null
    apparent_temperature: number | null
    shortwave_radiation: number | null
  }
} & { [Target in ForecastTarget]: number }
  & { [Target in ForecastTarget as `${Target}_p05`]: number }
  & { [Target in ForecastTarget as `${Target}_p95`]: number }

export type ForecastResponse = {
  generated_at: string
  data_as_of: string
  model_input_source: 'LIVE_ACTUALS' | 'HISTORICAL_BASELINE'
  data_freshness: DataFreshness
  weather_source: string
  location: string
  interval_minutes: number
  horizon_hours: number
  forecast: ForecastRow[]
  asset_simulations: AssetSimulationResult
  dispatch_target: ForecastTarget
  contracted_ppa_mw: number[] | null
  ramp_thresholds_mw: Record<ForecastTarget, { p75: number; p95: number }>
  ramp_summary: Record<ForecastTarget, RampAssessment & { timestamp: string | null }>
  thermal_coal_burn: {
    label: string
    energy_mwh: number
    estimated_coal_burn_tonnes: number
    thermal_mix_share: number
    specific_consumption_tonnes_per_mwh: number
    basis_note: string
  }
  reserve_policy: {
    minimum_p50_fraction: number
    basis_note: string
  }
  summary: {
    current_mw: number
    peak_mw: number
    average_mw: number
    estimated_thermal_coal_burn_tonnes: number
  }
}
