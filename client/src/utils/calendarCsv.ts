import { type CalendarData, type CalendarView } from '../types/calendar'
import { anomalyRatio } from './calendarScale'

/**
 * Builds a CSV of the calendar: one row per loaded month with its count, the
 * median for that month and the ratio to it. Empty fields mean "not
 * available" (no median yet). The harmonized view adds the source of each
 * month and the raw counts behind it, so the value can be checked by hand.
 */
export function buildCalendarCsv(
  data: CalendarData,
  view: CalendarView,
): string {
  const extra = data.harmonized
    ? ',source,modis_eq,terra,aqua,viirs_day,viirs_night,modis_raw,viirs_raw,low_count'
    : ''
  const header = `series,year,month,count,partial,monthly_median,ratio_to_median${extra}`
  const lines = data.months.map((m) => {
    const median = data.monthly_median[m.month - 1]
    const ratio = m.partial ? null : anomalyRatio(m.count, median)
    const row = [
      view,
      m.year,
      m.month,
      m.count,
      m.partial,
      median ?? '',
      ratio === null ? '' : ratio.toFixed(3),
    ]
    if (data.harmonized) {
      row.push(
        m.source ?? '',
        m.modis_eq ?? '',
        m.terra ?? '',
        m.aqua ?? '',
        m.viirs_day ?? '',
        m.viirs_night ?? '',
        m.modis,
        m.viirs,
        m.low_count ?? '',
      )
    }
    return row.join(',')
  })
  return [header, ...lines].join('\n') + '\n'
}
