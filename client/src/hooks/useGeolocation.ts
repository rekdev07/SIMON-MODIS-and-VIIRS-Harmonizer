import { useCallback, useEffect, useState } from 'react'
import { type LatLngPoint } from '../types/hotspots'

/** Approximate center of Durango city, used when the user's location is unavailable. */
export const DURANGO_CENTER: LatLngPoint = { lat: 24.0277, lng: -104.6532 }

/**
 * - `locating`: waiting for the browser (it may be showing the permission prompt)
 * - `located`: `position` is the user's location
 * - `fallback`: denied, failed or unsupported; `position` is {@link DURANGO_CENTER}
 */
export type GeolocationStatus = 'locating' | 'located' | 'fallback'

/** Value returned by {@link useGeolocation}. */
export type UseGeolocationResult = {
  position: LatLngPoint
  status: GeolocationStatus
  /** Asks the browser for the location again (e.g. from a "Use my location" button). */
  request: () => void
}

const isSupported = () =>
  typeof navigator !== 'undefined' && 'geolocation' in navigator

/**
 * Asks the browser for the user's position on mount (which triggers the
 * permission prompt) and falls back to Durango's center when permission is
 * denied, the lookup fails or geolocation is not supported. The position is
 * therefore always usable as a map center.
 */
export function useGeolocation(): UseGeolocationResult {
  const [position, setPosition] = useState<LatLngPoint>(DURANGO_CENTER)
  const [status, setStatus] = useState<GeolocationStatus>(() =>
    isSupported() ? 'locating' : 'fallback',
  )

  const locate = useCallback(() => {
    if (!isSupported()) return
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPosition({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setStatus('located')
      },
      () => setStatus('fallback'),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    )
  }, [])

  useEffect(() => {
    locate()
  }, [locate])

  const request = useCallback(() => {
    if (!isSupported()) return
    setStatus('locating')
    locate()
  }, [locate])

  return { position, status, request }
}
