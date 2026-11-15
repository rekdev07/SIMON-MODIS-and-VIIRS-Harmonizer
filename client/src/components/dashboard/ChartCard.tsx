import { type ReactNode, useRef, useState } from 'react'
import { ImageDown } from 'lucide-react'
import { downloadElementPng } from '../../utils/download'

/** Props of {@link ChartCard}. */
type ChartCardProps = {
  /** Dashboard chart number(s), e.g. `"2"` or `"13"`. */
  number: string
  title: string
  /** Short explanation shown under the title (units, what is plotted). */
  subtitle?: string
  loading: boolean
  /** API or network error message; replaces the chart. */
  error: string | null
  /**
   * Message shown instead of the chart when there is nothing to draw, usually
   * the API's "No data found in the selected area". Null when there is data.
   */
  emptyMessage: string | null
  /** Controls shown at the right of the title (selects, toggles). */
  actions?: ReactNode
  /** Make the card span the full dashboard width. */
  wide?: boolean
  children: ReactNode
}

/**
 * Frame of one dashboard chart: number, title, subtitle, optional controls and
 * the three non-data states.
 *
 * Order of precedence: error → loading (only before any data) → empty →
 * chart. While a refetch is running the previous chart stays visible but
 * dimmed, so the layout does not jump every time a filter changes.
 *
 * Every card with a chart has a PNG button that saves the whole card (title,
 * subtitle and chart), so the image still says what it shows once it is
 * pasted into a report. The controls are left out of the image.
 */
function ChartCard({
  number,
  title,
  subtitle,
  loading,
  error,
  emptyMessage,
  actions,
  wide = false,
  children,
}: ChartCardProps) {
  // Placeholder text replacing the chart, or null to draw the chart.
  let placeholder: { text: string; tone: string } | null = null
  if (error) {
    placeholder = { text: error, tone: 'text-red-600' }
  } else if (emptyMessage !== null) {
    placeholder = loading
      ? { text: 'Loading…', tone: 'text-gray-500' }
      : { text: emptyMessage, tone: 'text-gray-500' }
  }

  const cardRef = useRef<HTMLElement>(null)
  const [exporting, setExporting] = useState(false)

  const downloadPng = async () => {
    if (!cardRef.current) return
    const slug = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
    setExporting(true)
    try {
      await downloadElementPng(cardRef.current, `chart-${number}_${slug}.png`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <article
      ref={cardRef}
      className={`flex min-w-0 flex-col rounded border border-gray-300 bg-white p-4 ${wide ? 'lg:col-span-2' : ''}`}
    >
      <header className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-gray-900">
            <span className="mr-1.5 text-gray-400">#{number}</span>
            {title}
          </h3>
          {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
        </div>
        <div data-export-ignore className="flex shrink-0 gap-2">
          {actions}
          {!placeholder && (
            <button
              type="button"
              onClick={downloadPng}
              disabled={exporting}
              title="Download this chart as PNG"
              className="flex items-center gap-1 rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:text-gray-400"
            >
              <ImageDown size={14} /> {exporting ? '…' : 'PNG'}
            </button>
          )}
        </div>
      </header>
      <div
        className={`min-h-0 flex-1 transition-opacity ${loading && !error ? 'opacity-50' : ''}`}
        aria-busy={loading}
      >
        {placeholder ? (
          <p
            className={`flex h-72 items-center justify-center p-4 text-center text-sm ${placeholder.tone}`}
          >
            {placeholder.text}
          </p>
        ) : (
          children
        )}
      </div>
    </article>
  )
}

export default ChartCard
