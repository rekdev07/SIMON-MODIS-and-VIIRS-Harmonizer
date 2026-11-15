import { useState } from 'react'
import ConfidencePredictionForm from '../components/model/ConfidencePredictionForm'
import ModelPerformance from '../components/model/ModelPerformance'

type MachineLearningTab = 'prediction' | 'performance'

const TABS: { id: MachineLearningTab; label: string }[] = [
  { id: 'prediction', label: 'Prediction' },
  { id: 'performance', label: 'Performance' },
]

/** Machine-learning workspace for confidence inference and model evaluation. */
function MachineLearning() {
  const [tab, setTab] = useState<MachineLearningTab>('prediction')

  return (
    <div className="h-screen min-w-0 overflow-y-auto bg-gray-100 p-6">
      <header className="mb-5">
        <h2 className="text-lg font-bold text-gray-900">Machine Learning</h2>
        <p className="mt-1 text-xs text-gray-600">
          XGBoost random-forest classifier for VIIRS confidence.
        </p>
      </header>

      <div
        className="mb-5 inline-grid grid-cols-2 divide-x divide-gray-300 overflow-hidden rounded border border-gray-300 bg-white"
        role="tablist"
        aria-label="Machine learning view"
      >
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm font-medium ${
              tab === id
                ? 'bg-blue-600 text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'prediction' ? (
        <ConfidencePredictionForm />
      ) : (
        <ModelPerformance />
      )}
    </div>
  )
}

export default MachineLearning
