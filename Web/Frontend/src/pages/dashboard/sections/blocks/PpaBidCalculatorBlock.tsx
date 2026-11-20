import { Calculator } from 'lucide-react'
import { DashboardCard } from './DashboardCard'
type PpaBidCalculatorBlockProps = {
  contractMw: string
  onContractChange: (value: string) => void
  onApply: () => void
  applying: boolean
  error: string
}

export function PpaBidCalculatorBlock({
  contractMw,
  onContractChange,
  onApply,
  applying,
  error,
}: PpaBidCalculatorBlockProps) {
  const parsedContract = Number(contractMw)
  const isValid = contractMw.trim() !== '' && Number.isFinite(parsedContract) && parsedContract >= 0

  return (
    <DashboardCard title="PPA block comparison" icon={Calculator} className="dashboard-card--ppa">
      <label className="ppa-input-label" htmlFor="contracted-ppa-mw">Contracted PPA per 15-minute block (MW)</label>
      <input
        id="contracted-ppa-mw"
        className="ppa-input"
        type="number"
        min="0"
        step="0.1"
        inputMode="decimal"
        value={contractMw}
        onChange={(event) => onContractChange(event.target.value)}
      />
      <p className="dashboard-card-caption">
        Planning comparison only. This does not submit IEX bids or estimate DSM penalties.
      </p>
      {isValid ? (
        <div className="ppa-summary">
          <strong>Apply across the 96-block forecast</strong>
          <span>The API returns reserve, net position, and RTM buffer calculations for this area.</span>
        </div>
      ) : (
        <p className="ppa-validation" role="alert">Enter a non-negative contracted MW value to calculate block differences.</p>
      )}
      <button
        type="button"
        className="button button--outline"
        disabled={!isValid || applying}
        onClick={onApply}
      >
        {applying ? 'Calculating…' : 'Apply PPA schedule'}
      </button>
      {error && <p className="ppa-validation" role="alert">{error}</p>}
    </DashboardCard>
  )
}
