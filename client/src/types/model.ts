/** Normalized confidence labels shown in the UI and returned by the API. */
export type ConfidenceClass = 'low' | 'nominal' | 'high'

/** Raw VIIRS labels used by the trained XGBoost artifact. */
export type RawConfidenceClass = 'l' | 'n' | 'h'

/** Variable feature values sent to the confidence prediction endpoint. */
export type ModelPredictionRequest = {
  latitude: number
  longitude: number
  acq_date: string
  /** Four-digit UTC HHmm, preserving leading zeroes. */
  acq_time: string
  scan: number
  track: number
  daynight: 'D' | 'N'
  frp: number | null
  bright_t31: number
  type: '0' | '1' | '2' | '3'
  brightness: number
}

/** Prediction and calibrated-per-class probabilities returned by the API. */
export type ModelPrediction = {
  predicted_class: ConfidenceClass
  raw_class: RawConfidenceClass
  probabilities: Record<ConfidenceClass, number>
  model_version: string
}

/** Category vocabularies and fixed fields loaded from the model artifact. */
export type ModelFeatureSchema = {
  model_version: string
  categories: {
    acq_date: string[]
    acq_time: string[]
    daynight: Array<'D' | 'N'>
    version: string[]
    type: Array<'0' | '1' | '2' | '3'>
    instrument: string[]
    satellite: string[]
  }
  fixed_values: {
    version: string
    instrument: string
    satellite: string
  }
}

/** Per-class precision, recall, F1, and number of test examples. */
export type ClassMetrics = {
  precision: number
  recall: number
  'f1-score': number
  support: number
}

/** Evaluation report used by the model-performance view. */
export type ModelMetricsReport = {
  reporte: Record<
    RawConfidenceClass | 'accuracy' | 'macro avg' | 'weighted avg',
    ClassMetrics | number
  >
  /** Rows are actual classes; columns are predicted classes, in `classes` order. */
  confusion_matriz: number[][]
  classes: RawConfidenceClass[]
  n_test: number
  importancias: Record<string, number>
  model_version: string
}
