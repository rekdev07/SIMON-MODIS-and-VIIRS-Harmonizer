import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// Register only the pieces the dashboard uses, so the bundle stays smaller
// than importing the whole `echarts` package.
echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

/** ECharts option object accepted by {@link EChart}. */
export type EChartOption = echarts.EChartsCoreOption

/** Props of {@link EChart}. */
type EChartProps = {
  option: EChartOption
  /** Tailwind height class of the chart area (ECharts needs an explicit height). */
  heightClass?: string
}

/**
 * Thin React wrapper around an ECharts instance.
 *
 * How: the instance is created once per mounted `div`, `setOption` replaces
 * the whole option on every change (`notMerge`, so series removed by a filter
 * really disappear), a `ResizeObserver` keeps the canvas in sync with the
 * card width, and the instance is disposed on unmount to free the canvas.
 * It renders at 2× or more so the chart's PNG download is sharp.
 */
function EChart({ option, heightClass = 'h-72' }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    // At least 2× resolution so the PNG export (also 2×) stays sharp on
    // ordinary 1× screens; high-DPI screens keep their own ratio.
    const chart = echarts.init(container, undefined, {
      devicePixelRatio: Math.max(window.devicePixelRatio, 2),
    })
    chartRef.current = chart
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(container)
    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true })
  }, [option])

  return <div ref={containerRef} className={`w-full ${heightClass}`} />
}

export default EChart
