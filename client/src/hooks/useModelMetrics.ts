import { useEffect, useState } from 'react'
import { ApiRequestError } from '../api/client'
import { fetchModelMetrics } from '../api/model'
import { type ModelMetricsReport } from '../types/model'

/** Loading, data, and error state for {@link useModelMetrics}. */
export type UseModelMetricsResult = {
  report: ModelMetricsReport | null
  loading: boolean
  error: string | null
}

type State = {
  report: ModelMetricsReport | null
  error: string | null
  completed: boolean
}

/**
 * Loads the stored classifier evaluation report when the performance tab opens.
 *
 * Requests are abortable so leaving the view cannot update stale state.
 */
export function useModelMetrics(): UseModelMetricsResult {
  const [state, setState] = useState<State>({
    report: null,
    error: null,
    completed: false,
  })

  useEffect(() => {
    const controller = new AbortController()
    fetchModelMetrics(controller.signal)
      .then((report) => setState({ report, error: null, completed: true }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({
          report: null,
          error:
            err instanceof ApiRequestError
              ? err.message
              : 'Unexpected error while loading model metrics.',
          completed: true,
        })
      })
    return () => controller.abort()
  }, [])

  return {
    report: state.report,
    loading: !state.completed,
    error: state.error,
  }
}
