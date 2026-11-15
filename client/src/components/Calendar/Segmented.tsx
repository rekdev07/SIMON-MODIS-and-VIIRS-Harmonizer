/** Props of {@link Segmented}. */
type SegmentedProps<T extends string> = {
  /** Accessible name of the group, e.g. "Sensor". */
  label: string
  options: readonly (readonly [T, string])[]
  value: T
  onChange: (value: T) => void
}

/**
 * Small segmented control (a radio group drawn as joined buttons) used by the
 * calendar for its sensor and color-mode switches.
 */
function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="flex rounded-lg bg-gray-200 p-0.5 text-xs"
    >
      {options.map(([option, text]) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={value === option}
          onClick={() => onChange(option)}
          className={`rounded-md px-3 py-1 transition ${
            value === option
              ? 'bg-white font-semibold shadow'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          {text}
        </button>
      ))}
    </div>
  )
}

export default Segmented
