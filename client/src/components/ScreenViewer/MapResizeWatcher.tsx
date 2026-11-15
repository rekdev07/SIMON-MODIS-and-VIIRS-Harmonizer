import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

/**
 * Keeps Leaflet in sync with its container size.
 *
 * Why: Leaflet measures its container only on window resize. When a panel
 * (such as the burning calendar) opens below the map, the container shrinks
 * without a window resize and tiles end up misplaced. A `ResizeObserver` on
 * the container calls `invalidateSize()` whenever its box changes.
 */
function MapResizeWatcher() {
  const map = useMap()

  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])

  return null
}

export default MapResizeWatcher
