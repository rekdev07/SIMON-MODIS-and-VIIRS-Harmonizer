import { useMemo } from 'react'
import EChart, { type EChartOption } from '../dashboard/EChart'
import { useModelMetrics } from '../../hooks/useModelMetrics'
import {
  type ClassMetrics,
  type ModelMetricsReport,
  type RawConfidenceClass,
} from '../../types/model'

const CLASS_LABELS: Record<RawConfidenceClass, string> = {
  l: 'Low',
  n: 'Nominal',
  h: 'High',
}

function classMetrics(
  report: ModelMetricsReport,
  label: RawConfidenceClass | 'macro avg' | 'weighted avg',
): ClassMetrics | null {
  const value = report.reporte[label]
  return typeof value === 'object' && value !== null ? value : null
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded border border-gray-300 bg-white p-4">
      <p className="text-xs font-medium tracking-wide text-gray-500 uppercase">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-gray-900 tabular-nums">
        {value}
      </p>
    </article>
  )
}

function confusionOption(report: ModelMetricsReport): EChartOption {
  const labels = report.classes.map((value) => CLASS_LABELS[value])
  const data = report.confusion_matriz.flatMap((row, actual) =>
    row.map((count, predicted) => [predicted, actual, count]),
  )
  const maxValue = Math.max(...report.confusion_matriz.flat())

  return {
    animation: false,
    tooltip: { position: 'top' },
    grid: { top: 20, right: 24, bottom: 60, left: 100 },
    xAxis: {
      type: 'category',
      name: 'Predicted confidence',
      nameLocation: 'middle',
      nameGap: 38,
      data: labels,
    },
    yAxis: {
      type: 'category',
      name: 'Actual confidence',
      nameLocation: 'middle',
      nameGap: 72,
      data: labels,
    },
    visualMap: {
      min: 0,
      max: maxValue,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    series: [
      {
        type: 'heatmap',
        data,
        label: { show: true, color: '#111827' },
        emphasis: { itemStyle: { borderColor: '#1d4ed8', borderWidth: 1 } },
      },
    ],
  }
}

function importanceOption(report: ModelMetricsReport): EChartOption {
  const entries = Object.entries(report.importancias).sort(
    ([, left], [, right]) => left - right,
  )

  return {
    animation: false,
    grid: { top: 12, right: 24, bottom: 32, left: 120 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value',
      name: 'Importance',
      axisLabel: { formatter: (value: number) => value.toFixed(2) },
    },
    yAxis: {
      type: 'category',
      data: entries.map(([name]) => name),
      axisLabel: { width: 110, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        data: entries.map(([, value]) => value),
        itemStyle: { color: '#2563eb' },
      },
    ],
  }
}

/**
 * Renders evaluation metrics, class-level scores, confusion matrix, and
 * feature importances from the saved model report.
 */
function ModelPerformance() {
  const { report, loading, error } = useModelMetrics()
  const heatmap = useMemo(
    () => (report ? confusionOption(report) : null),
    [report],
  )
  const importance = useMemo(
    () => (report ? importanceOption(report) : null),
    [report],
  )

  if (loading && !report) {
    return (
      <p className="py-12 text-center text-sm text-gray-600">
        Loading model report…
      </p>
    )
  }
  if (error) {
    return (
      <p
        className="rounded border border-red-300 bg-white p-5 text-sm text-red-700"
        role="alert"
      >
        {error}
      </p>
    )
  }
  if (!report || !heatmap || !importance) return null

  const accuracy = report.reporte.accuracy
  const macro = classMetrics(report, 'macro avg')
  const weighted = classMetrics(report, 'weighted avg')

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-600">
        Evaluation set: {report.n_test.toLocaleString()} samples ·{' '}
        {report.model_version}. The confusion-matrix rows are actual classes;
        columns are predicted classes.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Accuracy"
          value={
            typeof accuracy === 'number'
              ? `${(accuracy * 100).toFixed(1)}%`
              : '—'
          }
        />
        <MetricCard
          label="Macro F1"
          value={macro ? `${(macro['f1-score'] * 100).toFixed(1)}%` : '—'}
        />
        <MetricCard
          label="Weighted F1"
          value={weighted ? `${(weighted['f1-score'] * 100).toFixed(1)}%` : '—'}
        />
        <MetricCard
          label="Test samples"
          value={report.n_test.toLocaleString()}
        />
      </div>

      <section className="overflow-x-auto rounded border border-gray-300 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-900">
          Metrics by confidence class
        </h3>
        <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-xs text-gray-500 uppercase">
              <th className="py-2 pr-4">Class</th>
              <th className="px-3 py-2">Precision</th>
              <th className="px-3 py-2">Recall</th>
              <th className="px-3 py-2">F1</th>
              <th className="px-3 py-2 text-right">Support</th>
            </tr>
          </thead>
          <tbody>
            {report.classes.map((rawClass) => {
              const metrics = classMetrics(report, rawClass)
              if (!metrics) return null
              return (
                <tr key={rawClass} className="border-b border-gray-100">
                  <th className="py-2 pr-4 font-medium">
                    {CLASS_LABELS[rawClass]}
                  </th>
                  <td className="px-3 py-2 tabular-nums">
                    {(metrics.precision * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {(metrics.recall * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {(metrics['f1-score'] * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {metrics.support.toLocaleString()}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="min-w-0 rounded border border-gray-300 bg-white p-4">
          <h3 className="text-sm font-semibold text-gray-900">
            Confusion matrix
          </h3>
          <EChart option={heatmap} heightClass="h-80" />
        </section>
        <section className="min-w-0 rounded border border-gray-300 bg-white p-4">
          <h3 className="text-sm font-semibold text-gray-900">
            Feature importance
          </h3>
          <EChart option={importance} heightClass="h-[30rem]" />
        </section>
      </div>
    </div>
  )
}

export default ModelPerformance
