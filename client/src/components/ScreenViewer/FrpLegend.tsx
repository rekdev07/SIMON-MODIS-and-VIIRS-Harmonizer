import { FRP_STEPS, FRP_UNKNOWN_COLOR } from '../../utils/frpColor'

/**
 * Floating legend explaining the hotspot colors (Fire Radiative Power in MW).
 * Reads the same `FRP_STEPS` as the markers, so it can never drift from them.
 */
function FrpLegend() {
  return (
    <div className="absolute bottom-6 left-3 z-[1000] rounded border border-gray-300 bg-gray-50/95 p-3 text-xs text-gray-700">
      <p className="mb-1.5 font-semibold">Fire intensity (FRP, MW)</p>
      <ul className="flex flex-col gap-1">
        {FRP_STEPS.map((step) => (
          <li key={step.label} className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full border border-gray-700/40"
              style={{ backgroundColor: step.color }}
            />
            {step.label}
          </li>
        ))}
        <li className="flex items-center gap-2">
          <span
            className="h-3 w-3 rounded-full border border-gray-700/40"
            style={{ backgroundColor: FRP_UNKNOWN_COLOR }}
          />
          Unknown
        </li>
      </ul>
    </div>
  )
}

export default FrpLegend
