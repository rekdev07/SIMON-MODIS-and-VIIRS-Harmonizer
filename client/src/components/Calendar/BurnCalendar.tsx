import { type CSSProperties, useMemo, useState } from 'react'
import { Download } from 'lucide-react'
import {
  type CalendarData,
  type CalendarMonth,
  type CalendarView,
  type DateRange,
  type HarmonizedSource,
} from '../../types/calendar'
import {
  ANOMALY_SCALE,
  NO_REFERENCE_COLOR,
  ZERO_COLOR,
  anomalyRatio,
  buildCountScale,
  formatCount,
  stepFor,
} from '../../utils/calendarScale'
import { buildCalendarCsv, downloadText } from '../../utils/calendarCsv'
import LegendSwatch from './LegendSwatch'
import Segmented from './Segmented'

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/** Hatching for months outside the loaded data ("no data", not "no fires"). */
const NO_DATA_STYLE: CSSProperties = {
  backgroundImage:
    'repeating-linear-gradient(45deg, #e5e7eb 0 2px, #f9fafb 2px 6px)',
}

/** Light hatching laid over a color to mark a partially loaded month. */
const PARTIAL_OVERLAY =
  'repeating-linear-gradient(45deg, rgba(255,255,255,0.55) 0 2px, transparent 2px 6px)'

type Mode = 'counts' | 'anomaly'

/**
 * Color and label of each harmonized source. Drawn as a thin bar at the
 * bottom of each month so the heat colors stay readable.
 */
const SOURCE_STYLE: Record<HarmonizedSource, { color: string; label: string }> =
  {
    terra_scaled: { color: '#7b3294', label: 'Terra × factor' },
    modis: { color: '#4b5563', label: 'MODIS' },
    average: { color: '#1b9e77', label: 'Average MODIS + VIIRS eq' },
    viirs_eq: { color: '#2b8cbe', label: 'VIIRS eq' },
  }

/** Props of {@link BurnCalendar}. */
type BurnCalendarProps = {
  data: CalendarData
  /** Month currently shown on the map, highlighted in the grid. */
  selected: { year: number; month: number } | null
  /** Dates of the last search; months touching it get a dashed outline. */
  range: DateRange | null
  /** Called when the user clicks a month with data. */
  onSelectMonth: (year: number, month: number) => void
  /** Harmonized series, or raw counts of one sensor (never MODIS + VIIRS raw). */
  view: CalendarView
  onViewChange: (view: CalendarView) => void
}

const VIEW_OPTIONS = [
  ['HARMONIZED', 'Harmonized'],
  ['MODIS', 'MODIS raw'],
  ['VIIRS', 'VIIRS raw'],
] as const

const MODE_OPTIONS = [
  ['counts', 'Counts'],
  ['anomaly', 'vs. median'],
] as const

/** Explains where a harmonized value comes from, with the raw counts behind it. */
function describeSource(m: CalendarMonth): string {
  switch (m.source) {
    case 'terra_scaled':
      return `source Terra × factor (Terra ${m.terra ?? 0})`
    case 'modis':
      return `source MODIS (Terra ${m.terra ?? 0} + Aqua ${m.aqua ?? 0})`
    case 'average':
      return `source average of MODIS ${m.modis} and VIIRS eq ${m.modis_eq ?? 0} (VIIRS raw ${m.viirs})`
    case 'viirs_eq':
      return `source VIIRS eq (VIIRS raw ${m.viirs})`
    default:
      return ''
  }
}

/**
 * Whether a month overlaps an inclusive date range. Comparing `YYYY-MM`
 * strings is enough: a month overlaps when it is between the range's first
 * and last month (ISO strings sort like dates).
 */
function monthInRange(year: number, month: number, range: DateRange | null) {
  if (!range) return false
  const key = `${year}-${String(month).padStart(2, '0')}`
  return key >= range.start.slice(0, 7) && key <= range.end.slice(0, 7)
}

/** Text describing one month, used for the hover line and `title`. */
function describe(m: CalendarMonth, median: number | null): string {
  const name = `${MONTH_LABELS[m.month - 1]} ${m.year}`
  const parts = m.source
    ? [
        `${name}: ${m.count.toLocaleString()} (MODIS-equivalent hotspots)`,
        describeSource(m),
      ]
    : [`${name}: ${m.count.toLocaleString()} hotspots`]
  if (m.low_count) parts.push('low count: larger error')
  if (m.partial) {
    parts.push('partial month (only some days loaded)')
  } else if (median !== null) {
    const ratio = anomalyRatio(m.count, median)
    parts.push(
      `median ${Math.round(median).toLocaleString()}` +
        (ratio === null ? '' : ` (${ratio.toFixed(2)}×)`),
    )
  }
  return parts.join(' · ')
}

/**
 * Burning activity calendar: a year × month heatmap of hotspot counts for the
 * selected area, with yearly totals on the right and the monthly median at the
 * bottom.
 *
 * How to read it: a fire season shows up as a dark vertical band, an unusual
 * year as a darker row. "Counts" colors each month by its number of hotspots;
 * "vs. median" colors it by `count / median of that month`, so months above
 * normal turn red and below normal turn blue.
 *
 * Honesty rules: hatched gray = no data loaded (different from a light "0"
 * cell, which means observed with no fires); light hatching over a color =
 * partial month, left out of medians and anomalies.
 *
 * Views: "Harmonized" (default) shows one continuous series in MODIS
 * Terra+Aqua units: the server converts VIIRS (375 m pixels, ~4× more
 * detections) to MODIS units with ratios fitted on the overlap years, so
 * there is no artificial jump in 2002 (Aqua) or 2012 (VIIRS). A colored bar
 * under each month tells its source. "MODIS raw" / "VIIRS raw" show one
 * sensor's raw counts; they are never added together.
 *
 * The calendar always covers the whole loaded history (medians need every
 * year); the months of the searched date range get a dashed outline so they
 * stand out from the rest.
 */
function BurnCalendar({
  data,
  selected,
  range,
  onSelectMonth,
  view,
  onViewChange,
}: BurnCalendarProps) {
  const [mode, setMode] = useState<Mode>('counts')
  const [hovered, setHovered] = useState<CalendarMonth | null>(null)

  const byKey = useMemo(
    () => new Map(data.months.map((m) => [`${m.year}-${m.month}`, m])),
    [data.months],
  )
  const countScale = useMemo(
    () => buildCountScale(Math.max(0, ...data.months.map((m) => m.count))),
    [data.months],
  )
  const yearList = data.years
  const maxYear = Math.max(1, ...yearList.map((y) => y.count))
  const latestFull = data.months.findLast((m) => !m.partial) ?? null
  const hasMedian = data.monthly_median.some((v) => v !== null)
  const fullYears = new Set(
    data.months.filter((m) => !m.partial).map((m) => m.year),
  ).size

  const cellStyle = (m: CalendarMonth): CSSProperties => {
    let color: string
    if (m.count === 0) {
      color = ZERO_COLOR
    } else if (mode === 'counts') {
      color = stepFor(countScale, m.count).color
    } else {
      const ratio = m.partial
        ? null
        : anomalyRatio(m.count, data.monthly_median[m.month - 1])
      color =
        ratio === null
          ? NO_REFERENCE_COLOR
          : stepFor(ANOMALY_SCALE, ratio).color
    }
    let text = '#374151'
    if (m.count > 0 && color !== NO_REFERENCE_COLOR) {
      const scale = mode === 'counts' ? countScale : ANOMALY_SCALE
      text = scale.find((s) => s.color === color)?.text ?? text
    }
    return {
      backgroundColor: color,
      color: text,
      backgroundImage: m.partial ? PARTIAL_OVERLAY : undefined,
    }
  }

  const download = () => {
    const [w, s, e, n] = data.bbox
    downloadText(
      `burn-calendar_${view}_${s}_${w}_${n}_${e}.csv`,
      buildCalendarCsv(data, view),
    )
  }

  const latestMedian = latestFull
    ? data.monthly_median[latestFull.month - 1]
    : null
  const latestRatio = latestFull && anomalyRatio(latestFull.count, latestMedian)
  const harmonization = data.harmonization
  const reliability = harmonization?.reliability
  const sourcesUsed = new Set(data.months.map((m) => m.source))
  const viewLabel =
    view === 'HARMONIZED'
      ? 'Harmonized (MODIS Terra+Aqua units)'
      : `${view} raw`

  return (
    <section className="flex flex-col gap-3 text-sm text-gray-800">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold">Burning activity calendar</h2>
          <p className="text-xs text-gray-600">
            {viewLabel} hotspots per month in the selected area
            {data.coverage &&
              ` · data from ${data.coverage.start_date} to ${data.coverage.end_date}`}
          </p>
          {harmonization ? (
            <p className="mt-1 text-xs text-gray-600">
              VIIRS → MODIS: day ÷ {harmonization.r_day?.toFixed(2)}, night ÷{' '}
              {harmonization.r_night?.toFixed(2)} (fitted{' '}
              {harmonization.fit_period.start_date.slice(0, 4)}–
              {harmonization.fit_period.end_date.slice(0, 4)}); before Aqua:
              Terra × {harmonization.terra_factor?.toFixed(2)}. Vegetation fires
              only.
            </p>
          ) : (
            <p className="mt-1 inline-block rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
              Raw {view} counts: not comparable with the other sensor. Use
              Harmonized for one continuous record.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            label="Series"
            options={VIEW_OPTIONS}
            value={view}
            onChange={onViewChange}
          />
          <Segmented
            label="Color by"
            options={MODE_OPTIONS}
            value={mode}
            onChange={setMode}
          />
          <button
            type="button"
            onClick={download}
            className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-xs text-white transition hover:bg-blue-500"
          >
            <Download size={14} /> CSV
          </button>
        </div>
      </header>

      {data.message && (
        <p className="rounded bg-gray-100 px-3 py-2 text-xs text-gray-700">
          {data.coverage
            ? `${data.message} (${viewLabel}).`
            : `No ${view === 'HARMONIZED' ? '' : `${view} `}data is loaded in the database yet.`}
        </p>
      )}

      {reliability &&
        harmonization &&
        data.total > 0 &&
        (reliability.small_area || reliability.low_count) && (
          <p
            role="alert"
            className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
          >
            <span className="font-semibold">Larger error in this area: </span>
            {reliability.small_area &&
              `it is smaller than ~1° × 1° (about 110 km a side; this one is ${reliability.area_deg2.toFixed(2)} square degrees). `}
            {reliability.low_count &&
              `A typical month has ${reliability.typical_month.toLocaleString()} hotspots, below the ${harmonization.min_reliable_count} per month from which the conversion error stays under ~30%. `}
            {reliability.low_count_months > 0 &&
              `${reliability.low_count_months} months are below that count. `}
            Read single months with care; trends over several months or years
            are more reliable.
          </p>
        )}

      {latestFull && (
        <p className="rounded bg-gray-100 px-3 py-2 text-xs">
          <span className="font-semibold">
            Latest full month, {MONTH_LABELS[latestFull.month - 1]}{' '}
            {latestFull.year}:
          </span>{' '}
          {latestFull.count.toLocaleString()} hotspots
          {latestRatio !== null && latestMedian !== null && (
            <>
              {' '}
              ({latestRatio.toFixed(2)}× the{' '}
              {MONTH_LABELS[latestFull.month - 1]} median of{' '}
              {Math.round(latestMedian).toLocaleString()})
            </>
          )}
          {fullYears < 2 && (
            <span className="text-gray-500">
              {' '}
              · Only {fullYears} year of data is loaded, so the median equals
              that year. Load more years to see real anomalies.
            </span>
          )}
        </p>
      )}

      {range && data.months.length > 0 && (
        <p className="text-xs text-gray-600">
          <span className="mr-1 inline-block h-3 w-4 rounded-sm align-middle outline-2 -outline-offset-2 outline-gray-900 outline-dashed" />
          Months in the selected range ({range.start} → {range.end}). The rest
          of the history stays visible for comparison.
        </p>
      )}

      {data.months.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-separate border-spacing-0.5 text-xs">
              <thead>
                <tr>
                  <th className="w-12" />
                  {MONTH_LABELS.map((label) => (
                    <th key={label} className="font-medium text-gray-500">
                      {label}
                    </th>
                  ))}
                  <th className="pl-2 text-left font-medium text-gray-500">
                    Year total
                  </th>
                </tr>
              </thead>
              <tbody>
                {yearList.map((year) => (
                  <tr key={year.year}>
                    <th className="pr-1 text-right font-medium text-gray-600">
                      {year.year}
                    </th>
                    {MONTH_LABELS.map((label, i) => {
                      const m = byKey.get(`${year.year}-${i + 1}`)
                      if (!m) {
                        return (
                          <td
                            key={label}
                            className="h-7 rounded-sm"
                            style={NO_DATA_STYLE}
                            title={`${label} ${year.year}: no data loaded`}
                          />
                        )
                      }
                      const isSelected =
                        selected?.year === m.year && selected.month === m.month
                      const inRange = monthInRange(m.year, m.month, range)
                      const text =
                        describe(m, data.monthly_median[i]) +
                        (inRange ? ' · in the selected range' : '')
                      return (
                        <td key={label} className="h-7 p-0">
                          <button
                            type="button"
                            onClick={() => onSelectMonth(m.year, m.month)}
                            onMouseEnter={() => setHovered(m)}
                            onMouseLeave={() => setHovered(null)}
                            onFocus={() => setHovered(m)}
                            onBlur={() => setHovered(null)}
                            title={text}
                            aria-label={`${text}. Show on map.`}
                            className={`relative h-full w-full rounded-sm tabular-nums transition hover:ring-2 hover:ring-gray-800 ${
                              isSelected ? 'ring-2 ring-blue-600' : ''
                            } ${
                              inRange
                                ? 'outline-2 -outline-offset-2 outline-gray-900 outline-dashed'
                                : ''
                            }`}
                            style={cellStyle(m)}
                          >
                            {m.count > 0 ? formatCount(m.count) : ''}
                            {m.source && (
                              // Source bar as an element, not a box-shadow, so it
                              // does not hide the hover/selected ring.
                              <span
                                aria-hidden
                                className="absolute inset-x-0 bottom-0 h-[3px]"
                                style={{
                                  backgroundColor: SOURCE_STYLE[m.source].color,
                                }}
                              />
                            )}
                          </button>
                        </td>
                      )
                    })}
                    <td className="pl-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 rounded-sm bg-gray-500"
                          style={{ width: `${(year.count / maxYear) * 80}px` }}
                        />
                        <span className="text-gray-700 tabular-nums">
                          {year.count.toLocaleString()}
                          {year.partial && (
                            <span className="text-gray-400"> (partial)</span>
                          )}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th className="pt-1 pr-1 text-right font-semibold text-gray-600">
                    Median
                  </th>
                  {data.monthly_median.map((value, i) => (
                    <td
                      key={MONTH_LABELS[i]}
                      className="pt-1 text-center font-semibold text-gray-700 tabular-nums"
                    >
                      {value === null ? '–' : formatCount(value)}
                    </td>
                  ))}
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>

          <p className="min-h-4 text-xs text-gray-600" aria-live="polite">
            {hovered
              ? describe(hovered, data.monthly_median[hovered.month - 1])
              : 'Hover a month for details; click it to show its hotspots on the map.'}
          </p>

          {mode === 'anomaly' && !hasMedian && (
            <p className="text-xs text-amber-700">
              No full month is loaded yet, so there is no median to compare
              with.
            </p>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600">
            <span className="font-semibold">
              {mode === 'counts' ? 'Hotspots' : 'Count ÷ monthly median'}
            </span>
            <LegendSwatch color={ZERO_COLOR} label="0" />
            {(mode === 'counts' ? countScale : ANOMALY_SCALE).map((step) => (
              <LegendSwatch
                key={step.label}
                color={step.color}
                label={step.label}
              />
            ))}
            {mode === 'anomaly' && (
              <LegendSwatch color={NO_REFERENCE_COLOR} label="No reference" />
            )}
            <span className="flex items-center gap-1">
              <span className="h-3 w-4 rounded-sm" style={NO_DATA_STYLE} /> No
              data
            </span>
            <span className="flex items-center gap-1">
              <span
                className="h-3 w-4 rounded-sm"
                style={{
                  backgroundColor: '#fd8d3c',
                  backgroundImage: PARTIAL_OVERLAY,
                }}
              />{' '}
              Partial month
            </span>
            {range && (
              <span className="flex items-center gap-1">
                <span className="h-3 w-4 rounded-sm outline-2 -outline-offset-2 outline-gray-900 outline-dashed" />
                Selected range
              </span>
            )}
          </div>
          {data.harmonized && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600">
              <span className="font-semibold">
                Source (bar under each month)
              </span>
              {(Object.keys(SOURCE_STYLE) as HarmonizedSource[])
                .filter((key) => sourcesUsed.has(key))
                .map((key) => (
                  <span key={key} className="flex items-center gap-1">
                    <span
                      className="h-1 w-4 rounded-sm"
                      style={{ backgroundColor: SOURCE_STYLE[key].color }}
                    />
                    {SOURCE_STYLE[key].label}
                  </span>
                ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}

export default BurnCalendar
