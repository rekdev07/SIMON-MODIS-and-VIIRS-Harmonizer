import { getJson, postJson } from './client'
import {
  type ModelMetricsReport,
  type ModelFeatureSchema,
  type ModelPrediction,
  type ModelPredictionRequest,
} from '../types/model'

/** Fetch the stored evaluation report used by the model-performance view. */
export function fetchModelMetrics(
  signal?: AbortSignal,
): Promise<ModelMetricsReport> {
  return getJson<ModelMetricsReport>('/api/v1/model/metrics', {}, signal)
}

/** Fetch categorical choices embedded in the served model artifact. */
export function fetchModelSchema(
  signal?: AbortSignal,
): Promise<ModelFeatureSchema> {
  return getJson<ModelFeatureSchema>('/api/v1/model/schema', {}, signal)
}

/** Ask the server-side XGBoost model to predict one hotspot's confidence. */
export function predictConfidence(
  input: ModelPredictionRequest,
  signal?: AbortSignal,
): Promise<ModelPrediction> {
  return postJson<ModelPrediction>('/api/v1/model/predict', input, signal)
}
