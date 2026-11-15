import { useEffect, useState } from 'react'
import { fetchDataset } from '../api/hotspots'
import { type DatasetInfo } from '../types/hotspots'

/**
 * Fetches the dataset summary once, used to bound the date pickers.
 * Failures are ignored on purpose: the UI then falls back to the API's
 * generic date window, and real errors surface when searching.
 */
export function useDataset(): DatasetInfo | null {
  const [dataset, setDataset] = useState<DatasetInfo | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchDataset(controller.signal)
      .then(setDataset)
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  return dataset
}
