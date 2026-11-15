import { type ReactNode } from 'react'

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

  return (
    <article
      className={`flex min-w-0 flex-col rounded-xl bg-white p-4 shadow-sm ${wide ? 'lg:col-span-2' : ''}`}
    >
      <header className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-gray-900">
            <span className="mr-1.5 text-gray-400">#{number}</span>
            {title}
          </h3>
          {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
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
