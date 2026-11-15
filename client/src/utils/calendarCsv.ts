import { type CalendarData } from '../types/calendar'
import { anomalyRatio } from './calendarScale'

/**
 * Builds a CSV of the calendar: one row per loaded month with its count,
 * the MODIS/VIIRS split, the median for that month and the ratio to it.
 * Empty fields mean "not available" (no median yet).
 */
export function buildCalendarCsv(data: CalendarData): string {
  const header =
    'year,month,count,modis,viirs,partial,monthly_median,ratio_to_median'
  const lines = data.months.map((m) => {
    const median = data.monthly_median[m.month - 1]
    const ratio = m.partial ? null : anomalyRatio(m.count, median)
    return [
      m.year,
      m.month,
      m.count,
      m.modis,
      m.viirs,
      m.partial,
      median ?? '',
      ratio === null ? '' : ratio.toFixed(3),
    ].join(',')
  })
  return [header, ...lines].join('\n') + '\n'
}

/**
 * Makes the browser save `text` as a file. A temporary object URL is used so
 * no server round trip is needed, and it is revoked right after the click.
 */
export function downloadText(
  filename: string,
  text: string,
  type = 'text/csv',
) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
