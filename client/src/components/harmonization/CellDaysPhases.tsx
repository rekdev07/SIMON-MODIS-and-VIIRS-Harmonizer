import { type CellDaysData, type CellDaysMetadata } from '../../types/stats'
import { formatNumber } from '../../utils/chartTheme'
import { CELL_DAYS_COLORS } from '../../utils/cellDays'

/** Props of {@link CellDaysPhases}. */
type CellDaysPhasesProps = {
  data: CellDaysData
  metadata: CellDaysMetadata
}

/** Plural-aware "N days". */
function days(n: number): string {
  return `${n.toLocaleString('en-US')} day${n === 1 ? '' : 's'}`
}

/**
 * Names the periods of the selection: which dates were extrapolated from
 * MODIS and which were observed by VIIRS SNPP, plus the share of the total
 * cell-days that each part contributes.
 *
 * The phases come from the API, which folds short VIIRS outages (filled with
 * Aqua) into the VIIRS period; those days are listed so nothing is hidden.
 */
function CellDaysPhases({ data, metadata }: CellDaysPhasesProps) {
  const { summary } = data
  const total = summary.value ?? 0
  const share = (part: number) =>
    total > 0 ? ` (${formatNumber((100 * part) / total, 0)} %)` : ''
  const harmonized = data.phases.some((p) => p.category === 'extrapolated')
  const filled = summary.days_aqua + summary.days_terra

  return (
    <section className="rounded border border-gray-300 bg-white p-4 lg:col-span-2">
      <h3 className="text-sm font-semibold text-gray-900">
        Harmonized and observed periods
      </h3>
      <p className="mb-3 text-xs text-gray-500">
        {harmonized || filled > 0
          ? 'Days without VIIRS SNPP data were extrapolated from MODIS: Aqua × ' +
            `${formatNumber(metadata.factors.Aqua, 3)}, or Terra × ` +
            `${formatNumber(metadata.factors.Terra, 3)} when Aqua is missing.`
          : 'VIIRS SNPP covers every day of the selection: no harmonization was needed.'}
      </p>
      <ul className="flex flex-col gap-2 text-sm">
        {data.phases.map((phase) => (
          <li key={phase.start} className="flex items-start gap-2">
            <span
              className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{
                backgroundColor:
                  phase.category === 'viirs'
                    ? CELL_DAYS_COLORS.viirs
                    : phase.category === 'extrapolated'
                      ? CELL_DAYS_COLORS.extrapolated
                      : '#d1d5db',
              }}
            />
            <div>
              <span className="font-medium text-gray-900">
                {phase.category === 'viirs'
                  ? 'Observed by VIIRS SNPP'
                  : phase.category === 'extrapolated'
                    ? 'Harmonized: extrapolated from MODIS'
                    : 'No satellite data'}
              </span>{' '}
              <span className="text-gray-700">
                {phase.start} → {phase.end} · {days(phase.days)}
              </span>
              <p className="text-xs text-gray-500">
                {[
                  phase.category !== 'viirs' &&
                    phase.days_terra > 0 &&
                    `Terra ${days(phase.days_terra)}`,
                  phase.category !== 'viirs' &&
                    phase.days_aqua > 0 &&
                    `Aqua ${days(phase.days_aqua)}`,
                  phase.category === 'viirs' &&
                    phase.days_aqua + phase.days_terra > 0 &&
                    `${days(phase.days_aqua + phase.days_terra)} filled from MODIS during VIIRS outages`,
                  phase.category === 'extrapolated' &&
                    phase.days_viirs > 0 &&
                    `${days(phase.days_viirs)} observed by VIIRS`,
                  phase.days_missing > 0 &&
                    `${days(phase.days_missing)} without any satellite data`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-gray-200 pt-2 text-xs text-gray-600">
        Total {formatNumber(total, 0)} cell-days: observed{' '}
        {formatNumber(summary.viirs, 0)}
        {share(summary.viirs)}, extrapolated{' '}
        {formatNumber(summary.extrapolated, 0)}
        {share(summary.extrapolated)}. Grid {metadata.cell_km} km ×{' '}
        {metadata.cell_km} km.
      </p>
    </section>
  )
}

export default CellDaysPhases
