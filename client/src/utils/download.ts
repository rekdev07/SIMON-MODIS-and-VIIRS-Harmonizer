import { toPng } from 'html-to-image'

/**
 * Attribute that marks elements (buttons, toggles) to leave out of PNG
 * exports: write `data-export-ignore` on them in JSX.
 */
const EXPORT_IGNORE_ATTR = 'data-export-ignore'

/**
 * Makes the browser save a URL (object URL or data URL) as a file by clicking
 * a temporary `<a download>` link. Nothing goes through the server.
 */
function saveUrl(filename: string, url: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
}

/**
 * Makes the browser save `text` as a file. A temporary object URL is used so
 * no server round trip is needed, and it is revoked right after the click.
 */
export function downloadText(
  filename: string,
  text: string,
  type = 'text/csv',
) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  saveUrl(filename, url)
  URL.revokeObjectURL(url)
}

/**
 * Saves what an element shows as a PNG image.
 *
 * How: `html-to-image` copies the element and its computed styles into an
 * SVG `foreignObject` and draws it on a canvas; ECharts canvases inside are
 * copied as images too, so one function serves the calendar table and every
 * dashboard chart. Elements carrying {@link EXPORT_IGNORE_ATTR} (the download
 * buttons themselves, toggles) are skipped. `pixelRatio: 2` keeps text sharp
 * on slides and reports, and the white background avoids a transparent PNG.
 * A scrollable element is exported at its full scroll width, so a wide
 * calendar is not cut at the screen edge.
 *
 * @param element - Element to capture.
 * @param filename - Name of the saved file, ending in `.png`.
 */
export async function downloadElementPng(
  element: HTMLElement,
  filename: string,
) {
  const dataUrl = await toPng(element, {
    pixelRatio: 2,
    backgroundColor: '#ffffff',
    width: element.scrollWidth,
    height: element.scrollHeight,
    filter: (node) =>
      !(node instanceof HTMLElement && node.hasAttribute(EXPORT_IGNORE_ATTR)),
  })
  saveUrl(filename, dataUrl)
}
