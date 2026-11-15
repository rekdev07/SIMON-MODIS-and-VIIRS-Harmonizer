/// <reference types="vite/client" />

/** Typed Vite environment variables used by the client. */
interface ImportMetaEnv {
  /** Base URL of the Hotspots API, e.g. `http://localhost:5000`. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
