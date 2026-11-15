import { useState, type FormEvent } from 'react'
import Button from '../fields/Button'
import { useModelPrediction } from '../../hooks/useModelPrediction'
import { useModelSchema } from '../../hooks/useModelSchema'
import {
  type ConfidenceClass,
  type ModelPredictionRequest,
} from '../../types/model'

type FormValues = {
  latitude: string
  longitude: string
  acq_date: string
  acq_time: string
  scan: string
  track: string
  daynight: 'D' | 'N'
  frp: string
  bright_t31: string
  type: '0' | '1' | '2' | '3'
  brightness: string
}

const INITIAL_VALUES: FormValues = {
  latitude: '16.1985',
  longitude: '-95.17513',
  acq_date: '2014-01-02',
  acq_time: '0701',
  scan: '0.77',
  track: '0.78',
  daynight: 'N',
  frp: '2.77',
  bright_t31: '287.73',
  type: '2',
  brightness: '303.23',
}

const CONFIDENCE_LABELS: Record<ConfidenceClass, string> = {
  low: 'Low',
  nominal: 'Nominal',
  high: 'High',
}
const CONFIDENCE_ORDER: ConfidenceClass[] = ['low', 'nominal', 'high']

type NumberFieldProps = {
  label: string
  name: keyof Pick<
    FormValues,
    | 'latitude'
    | 'longitude'
    | 'scan'
    | 'track'
    | 'frp'
    | 'bright_t31'
    | 'brightness'
  >
  value: string
  min?: number
  max?: number
  required?: boolean
  onChange: (name: NumberFieldProps['name'], value: string) => void
}

function NumberField({
  label,
  name,
  value,
  min,
  max,
  required = true,
  onChange,
}: NumberFieldProps) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
      {label}
      <input
        name={name}
        type="number"
        step="any"
        min={min}
        max={max}
        value={value}
        required={required}
        onChange={(event) => onChange(name, event.target.value)}
        className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 outline-none focus:border-blue-600"
      />
    </label>
  )
}

/**
 * Collects the model's variable input features and displays one prediction.
 *
 * The target `confidence` and the model's fixed `version`, `instrument`, and
 * `satellite` values are intentionally not editable or submitted.
 */
function ConfidencePredictionForm() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES)
  const prediction = useModelPrediction()
  const { schema, loading, error } = useModelSchema()

  if (loading) {
    return (
      <p className="py-12 text-center text-sm text-gray-600">
        Loading model input options…
      </p>
    )
  }
  if (error) {
    return (
      <p
        className="rounded border border-red-300 bg-white p-5 text-sm text-red-700"
        role="alert"
      >
        {error}
      </p>
    )
  }
  if (!schema) return null

  const dates = schema.categories.acq_date
  const times = schema.categories.acq_time
  const selectedDate = dates.includes(values.acq_date)
    ? values.acq_date
    : (dates[0] ?? '')
  const selectedTime = times.includes(values.acq_time)
    ? values.acq_time
    : (times[0] ?? '')

  const updateNumber = (name: NumberFieldProps['name'], value: string) => {
    setValues((current) => ({ ...current, [name]: value }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const input: ModelPredictionRequest = {
      latitude: Number(values.latitude),
      longitude: Number(values.longitude),
      acq_date: selectedDate,
      acq_time: selectedTime,
      scan: Number(values.scan),
      track: Number(values.track),
      daynight: values.daynight,
      frp: values.frp === '' ? null : Number(values.frp),
      bright_t31: Number(values.bright_t31),
      type: values.type,
      brightness: Number(values.brightness),
    }
    void prediction.predict(input)
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
      <form
        onSubmit={handleSubmit}
        className="rounded border border-gray-300 bg-white p-5"
      >
        <h3 className="mb-1 text-base font-semibold text-gray-900">
          VIIRS hotspot features
        </h3>
        <p className="mb-5 text-xs text-gray-600">
          Confidence is the prediction target and is not an input. Fixed model
          values: version {schema.fixed_values.version} · instrument{' '}
          {schema.fixed_values.instrument} · satellite{' '}
          {schema.fixed_values.satellite}.
        </p>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField
            label="Latitude"
            name="latitude"
            value={values.latitude}
            min={-90}
            max={90}
            onChange={updateNumber}
          />
          <NumberField
            label="Longitude"
            name="longitude"
            value={values.longitude}
            min={-180}
            max={180}
            onChange={updateNumber}
          />
          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Acquisition date
            <input
              name="acq_date"
              type="date"
              value={selectedDate}
              min={dates[0]}
              max={dates[dates.length - 1]}
              required
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  acq_date: event.target.value,
                }))
              }
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 outline-none focus:border-blue-600"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Acquisition time (UTC)
            <select
              name="acq_time"
              value={selectedTime}
              required
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  acq_time: event.target.value,
                }))
              }
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 outline-none focus:border-blue-600"
            >
              {times.map((time) => (
                <option key={time} value={time}>
                  {time.slice(0, 2)}:{time.slice(2)}
                </option>
              ))}
            </select>
          </label>
          <NumberField
            label="Scan (km)"
            name="scan"
            value={values.scan}
            min={0}
            onChange={updateNumber}
          />
          <NumberField
            label="Track (km)"
            name="track"
            value={values.track}
            min={0}
            onChange={updateNumber}
          />
          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Day / night
            <select
              name="daynight"
              value={values.daynight}
              onChange={(event) => {
                const value = event.target.value
                if (value === 'D' || value === 'N') {
                  setValues((current) => ({ ...current, daynight: value }))
                }
              }}
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 outline-none focus:border-blue-600"
            >
              <option value="D">Day (D)</option>
              <option value="N">Night (N)</option>
            </select>
          </label>
          <NumberField
            label="Fire radiative power (MW)"
            name="frp"
            value={values.frp}
            min={0}
            required={false}
            onChange={updateNumber}
          />
          <NumberField
            label="TIR brightness (K)"
            name="bright_t31"
            value={values.bright_t31}
            onChange={updateNumber}
          />
          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Fire type
            <select
              name="type"
              value={values.type}
              onChange={(event) => {
                const value = event.target.value
                if (
                  value === '0' ||
                  value === '1' ||
                  value === '2' ||
                  value === '3'
                ) {
                  setValues((current) => ({ ...current, type: value }))
                }
              }}
              className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm font-normal text-gray-900 outline-none focus:border-blue-600"
            >
              <option value="0">0 — vegetation</option>
              <option value="1">1 — volcano</option>
              <option value="2">2 — static source</option>
              <option value="3">3 — offshore</option>
            </select>
          </label>
          <NumberField
            label="MIR brightness (K)"
            name="brightness"
            value={values.brightness}
            onChange={updateNumber}
          />
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={prediction.loading}>
            {prediction.loading ? 'Predicting…' : 'Predict confidence'}
          </Button>
          {prediction.error && (
            <p className="text-sm text-red-700" role="alert">
              {prediction.error}
            </p>
          )}
        </div>
      </form>

      <section
        className="rounded border border-gray-300 bg-white p-5"
        aria-live="polite"
      >
        <h3 className="mb-1 text-base font-semibold text-gray-900">
          Prediction
        </h3>
        {prediction.result ? (
          <>
            <p className="mt-4 text-sm text-gray-600">Predicted confidence</p>
            <p className="text-3xl font-bold text-blue-700 capitalize">
              {prediction.result.predicted_class}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Model class {prediction.result.raw_class} ·{' '}
              {prediction.result.model_version}
            </p>
            <div className="mt-6 space-y-4">
              {CONFIDENCE_ORDER.map((label) => {
                const probability = prediction.result?.probabilities[label] ?? 0
                return (
                  <div key={label}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{CONFIDENCE_LABELS[label]}</span>
                      <span className="tabular-nums">
                        {(probability * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100">
                      <div
                        className="h-full bg-blue-600"
                        style={{ width: `${probability * 100}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
            <p className="mt-5 text-xs text-gray-500">
              Probabilities are the model&apos;s output scores and are not
              necessarily calibrated.
            </p>
          </>
        ) : (
          <p className="mt-4 text-sm text-gray-600">
            Submit the feature values to see the predicted class and its
            probability scores.
          </p>
        )}
      </section>
    </div>
  )
}

export default ConfidencePredictionForm
