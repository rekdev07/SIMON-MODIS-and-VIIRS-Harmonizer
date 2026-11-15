# Architecture proposal: confidence model and performance report

## Context and findings

The client is React/Vite and its main view switcher currently has Map,
Calendar, and Dashboard. The Flask API has no model or ML-report endpoints.
The repository does contain:

- `client/src/xgboost/modelXGB.json`: a native XGBoost JSON model with
  `multi:softprob`, 3 classes, and 14 named features in a fixed order.
- `client/src/xgboost/reporte.json`: per-class precision/recall/F1/support,
  accuracy, macro/weighted averages, a 3×3 confusion matrix, test size, and
  feature importances.

The model's classes are raw VIIRS labels `l`, `n`, and `h`. The agreed product
contract is to present normalized labels `low`, `nominal`, and `high`, mapping
explicitly between them. The form should not request `confidence`, since that
is the prediction target.

## Proposed architecture

- **One Machine Learning section:** Extend `MainView`/`ViewToggle` with one
  `Machine Learning` view. Inside it, provide two tabs: **Prediction** and
  **Performance**. Keep this separate from the existing map search and
  dashboard filters.
- **Backend-owned artifacts and inference:** Relocate the model and report
  from the client source tree to a versioned server-side model-artifact
  location. Add `POST /api/v1/model/predict` for inference and
  `GET /api/v1/model/metrics` for the evaluation report. The API, not the
  browser, loads/consumes the model. The metrics endpoint serves the report
  with an explicit schema and model/evaluation version. Missing or
  incompatible artifacts should produce a clear API error, not a fallback.
- **Model contract:** Keep the 14 feature names/order and categorical types
  consistent with the model JSON. The observed features are `latitude`,
  `longitude`, `acq_date`, `acq_time`, `scan`, `track`, `daynight`, `version`,
  `frp`, `bright_t31`, `type`, `instrument`, `satellite`, and `brightness`.
  The report shows only `version=2`, `instrument=SNPP`, and `satellite=SNPP`;
  keep those fixed/hidden for this model slice. Check compatibility of the
  saved categorical metadata and XGBoost version before choosing the Python
  loading/input construction path; the JSON is a native XGBoost model, not
  evidence of a complete sklearn preprocessing pipeline.
- **Prediction form:** Expose the 11 variable features above. Use selects for
  `daynight` (`D`/`N`) and `type` (`0`–`3`), date and HHmm time inputs, numeric
  controls for the remaining features, and coordinate validation. Do not
  invent sensor/physical bounds that are absent from the model's training
  contract. Exclude `confidence` from the request. The API injects the three
  fixed fields, constructs the model input in exact feature order, and maps
  `l/n/h` outputs and probabilities to `low/nominal/high`.
- **Metrics view:** Load the report through the typed API client. Visualize
  accuracy and macro/weighted F1 as summary cards; show per-class
  precision/recall/F1/support, the confusion matrix with true/predicted axes,
  and feature importances. Label the evaluation set size and model/report
  version. Reuse the client's existing charting dependency where suitable.
- **Client layering:** Add typed model request/response/report types, API
  wrappers, and hooks for loading/error/data. Keep components free of direct
  `fetch` calls. Lazy-load the ML section if it pulls charting code into the
  initial map bundle.
- **Input mapping:** Translate the training/raw names at the API boundary.
  Existing normalized fields correspond as follows: `brightness` →
  `bright_mir`, `bright_t31` → `bright_tir`, `scan` → `pixel_scan`, `track` →
  `pixel_track`, and `type` → `fire_type`. The prediction contract should
  preserve the model's original feature names rather than accidentally
  applying the hotspots API's normalized names to the model.
- **Validation and docs:** Test both endpoints, invalid inputs, model-loading
  failures, output class/probability mapping, and report shape. Document the
  model artifact/version and API contract. Verify frontend lint, format, and
  build plus backend tests.

## Implementation todos

1. Verify model loading compatibility, categorical handling, feature order,
   class-index mapping, dependency/version, and report schema.
2. Add the Flask model API for metrics and prediction, with server-side
   artifact loading and request/response validation.
3. Add the Machine Learning view with Prediction/Performance tabs, typed API
   integration, validated form, and metric visualizations.
4. Test and document the full model/report integration.

## Notes

- `reporte.json` orders classes as `l`, `n`, `h`; preserve that order when
  interpreting its confusion matrix and importances. The UI/API presentation
  maps those labels to `low`, `nominal`, `high`.
- The existing dashboard uses ECharts. Prefer reusing it for the confusion
  matrix and feature-importance chart instead of adding a charting dependency.
- The model artifact's feature metadata marks several inputs categorical,
  including date/time and `daynight`; model loading and request conversion
  must reproduce the exact training representation.
