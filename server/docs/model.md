# Confidence model

The Machine Learning view uses a server-side XGBoost multiclass model to predict
the confidence class of one VIIRS hotspot detection. The input feature is not
the target: never include `confidence` in a prediction request.

## Artifacts and configuration

The default server-side artifacts are:

- `server/model_artifacts/modelXGB.json`: native XGBoost model.
- `server/model_artifacts/reporte.json`: evaluation report for the model.

Override their locations with `CONFIDENCE_MODEL_PATH` and
`CONFIDENCE_MODEL_REPORT_PATH`. Relative paths are resolved from `server/`.
Install dependencies from `server/requirements.txt`; the native model uses
XGBoost 3.4.x categorical feature support and pandas data frames.

The model is loaded lazily by the API and cached in the process. It is not
retrained during requests. A missing, malformed, or incompatible artifact
produces an explicit `MODEL_UNAVAILABLE` API error.

## Feature contract

The model expects exactly these columns, in this order:

| Feature | Input |
| --- | --- |
| `latitude`, `longitude` | Numeric coordinates |
| `acq_date` | ISO date string, treated as categorical |
| `acq_time` | Four-digit UTC `HHmm` string, treated as categorical |
| `scan`, `track` | Positive numeric pixel dimensions |
| `daynight` | `D` or `N`, categorical |
| `version` | Fixed to `"2"` for this model |
| `frp` | Null or non-negative numeric value |
| `bright_t31` | Numeric TIR brightness |
| `type` | Categorical string `"0"` through `"3"` |
| `instrument`, `satellite` | Both fixed to `"SNPP"` for this model |
| `brightness` | Numeric MIR brightness |

The form submits the 11 variable features. The API adds the three fixed values,
constructs the feature frame in model order, and preserves the categorical
feature types stored in the XGBoost artifact. `GET /api/v1/model/schema`
extracts the categorical vocabularies from the artifact; this is important
because acquisition dates and times are categorical inputs, not arbitrary
values. The API rejects dates/times not seen during training, and the form
limits users to supported choices.

The normalized database schema uses different names for some values:
`brightness` maps to `bright_mir`, `bright_t31` to `bright_tir`, `scan` to
`pixel_scan`, `track` to `pixel_track`, and `type` to `fire_type`. The model API
accepts the model's training feature names and does not use the normalized
database names as model columns.

## Classes and output

The evaluation report defines model output order `l`, `n`, `h`. Those labels
map to normalized product labels `low`, `nominal`, `high`, respectively. The
inference response includes both the normalized `predicted_class` and `raw_class`
plus normalized probabilities for all three classes.

## Evaluation report

`GET /api/v1/model/metrics` serves the stored test-set report, not a live
re-evaluation. Its fields are:

- `reporte`: precision, recall, F1 and support for each raw class, plus accuracy,
  macro average and weighted average.
- `confusion_matriz`: 3×3 counts; rows are actual labels and columns predicted,
  in the `classes` order.
- `n_test`: number of held-out test examples.
- `importancias`: model feature importances.
- `model_version`: API identifier for the served artifact.

The report shows class imbalance and weaker precision for the raw `l` class than
for `n` and `h`. The dashboard displays the scores and confusion matrix so this
is visible; do not interpret overall accuracy alone as model quality. Model
probabilities are not presented as calibrated confidence intervals.

The current report covers 37,383 test examples and reports 85.3% accuracy.
For raw class `l` (shown as **Low**), precision is 43.4% and recall is 86.7%;
this makes the per-class metrics and confusion matrix important complements to
the aggregate score.
