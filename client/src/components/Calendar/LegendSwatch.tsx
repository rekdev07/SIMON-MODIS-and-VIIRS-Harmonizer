/** Props of {@link LegendSwatch}. */
type LegendSwatchProps = { color: string; label: string }

/** One colored square + label of the calendar legend. */
function LegendSwatch({ color, label }: LegendSwatchProps) {
  return (
    <span className="flex items-center gap-1">
      <span
        className="h-3 w-4 rounded-sm border border-gray-300"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  )
}

export default LegendSwatch
