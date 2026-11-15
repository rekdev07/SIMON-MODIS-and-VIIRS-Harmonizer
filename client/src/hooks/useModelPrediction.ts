import { useState } from 'react'
import { ApiRequestError } from '../api/client'
import { predictConfidence } from '../api/model'
import {
  type ModelPrediction,
  type ModelPredictionRequest,
} from '../types/model'

/** Prediction action and request state for {@link useModelPrediction}. */
export type UseModelPredictionResult = {
  result: ModelPrediction | null
  loading: boolean
  error: string | null
  predict: (input: ModelPredictionRequest) => Promise<void>
}

/** Runs a confidence prediction and exposes explicit loading and error state. */
export function useModelPrediction(): UseModelPredictionResult {
  const [result, setResult] = useState<ModelPrediction | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const predict = async (input: ModelPredictionRequest) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await predictConfidence(input))
    } catch (err: unknown) {
      setError(
        err instanceof ApiRequestError
          ? err.message
          : 'Unexpected error while predicting confidence.',
      )
    } finally {
      setLoading(false)
    }
  }

  return { result, loading, error, predict }
}
