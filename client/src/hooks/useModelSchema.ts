import { useEffect, useState } from 'react'
import { ApiRequestError } from '../api/client'
import { fetchModelSchema } from '../api/model'
import { type ModelFeatureSchema } from '../types/model'

/** Loading, data, and error state for {@link useModelSchema}. */
export type UseModelSchemaResult = {
  schema: ModelFeatureSchema | null
  loading: boolean
  error: string | null
}

/** Loads model-defined category vocabularies and fixed input values. */
export function useModelSchema(): UseModelSchemaResult {
  const [schema, setSchema] = useState<ModelFeatureSchema | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    fetchModelSchema(controller.signal)
      .then(setSchema)
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setError(
          err instanceof ApiRequestError
            ? err.message
            : 'Unexpected error while loading model input options.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [])

  return { schema, loading, error }
}
