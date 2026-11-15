/** One choice of a {@link MiniSelect}. */
export type MiniSelectOption = {
  value: string
  label: string
}

/** Props of {@link MiniSelect}. */
type MiniSelectProps = {
  /** Accessible name (also shown as a tooltip). */
  label: string
  value: string
  options: MiniSelectOption[]
  onChange: (value: string) => void
}

/** Compact `<select>` used in chart headers (frequency, metric, sensor...). */
function MiniSelect({ label, value, options, onChange }: MiniSelectProps) {
  return (
    <select
      aria-label={label}
      title={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 outline-none focus:border-blue-600"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export default MiniSelect
