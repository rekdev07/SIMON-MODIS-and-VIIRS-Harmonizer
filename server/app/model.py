"""Model artifact loading, request validation, and confidence inference."""

from __future__ import annotations

import json
import logging
import threading
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypedDict

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.errors import ModelUnavailableError

if TYPE_CHECKING:
    import xgboost as xgb

logger = logging.getLogger(__name__)

MODEL_VERSION = "xgbrf-confidence-v1"
FEATURE_NAMES: tuple[str, ...] = (
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "scan",
    "track",
    "daynight",
    "version",
    "frp",
    "bright_t31",
    "type",
    "instrument",
    "satellite",
    "brightness",
)
FEATURE_TYPES: tuple[str, ...] = (
    "float",
    "float",
    "c",
    "c",
    "float",
    "float",
    "c",
    "c",
    "float",
    "float",
    "c",
    "c",
    "c",
    "float",
)
CATEGORICAL_FEATURES: tuple[str, ...] = tuple(
    name for name, kind in zip(FEATURE_NAMES, FEATURE_TYPES, strict=True) if kind == "c"
)

RawConfidence = Literal["l", "n", "h"]
Confidence = Literal["low", "nominal", "high"]
RAW_TO_CONFIDENCE: dict[str, Confidence] = {
    "l": "low",
    "n": "nominal",
    "h": "high",
}

_MODEL_LOCK = threading.Lock()


class PredictionRequest(BaseModel):
    """Variable form fields accepted by the confidence model endpoint."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    acq_date: date
    acq_time: str = Field(pattern=r"^(?:[01]\d|2[0-3])[0-5]\d$")
    scan: float = Field(gt=0, allow_inf_nan=False)
    track: float = Field(gt=0, allow_inf_nan=False)
    daynight: Literal["D", "N"]
    frp: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    bright_t31: float = Field(allow_inf_nan=False)
    type: Literal["0", "1", "2", "3"]
    brightness: float = Field(allow_inf_nan=False)

    @field_validator("acq_date", mode="before")
    @classmethod
    def _strict_iso_date(cls, value: object) -> object:
        """Require a full calendar date so its categorical model value is stable."""
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError("must be a date in YYYY-MM-DD format")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("must be a valid date in YYYY-MM-DD format") from exc
        if parsed.isoformat() != value:
            raise ValueError("must be a date in YYYY-MM-DD format")
        return parsed


class ClassMetrics(BaseModel):
    """Precision, recall, F1, and support for one report class."""

    model_config = ConfigDict(populate_by_name=True)

    precision: float = Field(ge=0, le=1, allow_inf_nan=False)
    recall: float = Field(ge=0, le=1, allow_inf_nan=False)
    f1_score: float = Field(alias="f1-score", ge=0, le=1, allow_inf_nan=False)
    support: float = Field(ge=0, allow_inf_nan=False)


class ConfidenceModelReport(BaseModel):
    """Validated shape of the stored model evaluation report."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    classification: dict[str, ClassMetrics | float] = Field(alias="reporte")
    confusion_matrix: list[list[int]] = Field(alias="confusion_matriz")
    classes: list[RawConfidence]
    n_test: int = Field(gt=0)
    importances: dict[str, float] = Field(alias="importancias")

    @model_validator(mode="after")
    def _validate_report_shape(self) -> ConfidenceModelReport:
        """Keep the confusion matrix and class order aligned with model outputs."""
        if self.classes != ["l", "n", "h"]:
            raise ValueError("classes must be ordered as l, n, h")
        if len(self.confusion_matrix) != 3 or any(
            len(row) != 3 for row in self.confusion_matrix
        ):
            raise ValueError("confusion_matriz must be a 3-by-3 matrix")
        if set(FEATURE_NAMES) - self.importances.keys():
            raise ValueError("importancias must include every model feature")
        return self


class PredictionSchema(TypedDict):
    """Model input choices and fixed values exposed to the client."""

    model_version: str
    categories: dict[str, list[str]]
    fixed_values: dict[str, str]


def load_report(path: Path) -> ConfidenceModelReport:
    """Read and validate the model evaluation report.

    Args:
        path: Configured JSON report path.

    Returns:
        The validated report.

    Raises:
        ModelUnavailableError: If the report is missing, malformed, or incompatible.
    """
    try:
        with path.open(encoding="utf-8") as file:
            raw_report = json.load(file)
        return ConfidenceModelReport.model_validate(raw_report)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.exception("Could not load confidence model evaluation report")
        raise ModelUnavailableError("The confidence model report is not available") from exc


@lru_cache(maxsize=2)
def _load_prediction_schema(path_string: str) -> PredictionSchema:
    """Read the exact categorical vocabularies embedded in the native model."""
    path = Path(path_string)
    try:
        with path.open(encoding="utf-8") as file:
            serialized = json.load(file)
        learner = serialized["learner"]
        feature_names = tuple(learner["feature_names"])
        feature_types = tuple(learner["feature_types"])
        if feature_names != FEATURE_NAMES or feature_types != FEATURE_TYPES:
            raise ValueError("the model feature schema is incompatible")

        encoded = learner["gradient_booster"]["model"]["cats"]["enc"]
        categories: dict[str, list[str]] = {}
        for index, (name, kind) in enumerate(
            zip(FEATURE_NAMES, FEATURE_TYPES, strict=True)
        ):
            if kind != "c":
                continue
            entry = encoded[index]
            offsets = entry["offsets"]
            values = entry["values"]
            if len(offsets) < 2:
                raise ValueError(f"the category vocabulary for {name} is empty")
            categories[name] = [
                bytes(values[offsets[item] : offsets[item + 1]]).decode("utf-8")
                for item in range(len(offsets) - 1)
            ]
        fixed_values: dict[str, str] = {}
        for name in ("version", "instrument", "satellite"):
            choices = categories[name]
            if len(choices) != 1:
                raise ValueError(f"{name} must have exactly one model category")
            fixed_values[name] = choices[0]
        return {
            "model_version": MODEL_VERSION,
            "categories": categories,
            "fixed_values": fixed_values,
        }
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
    ) as exc:
        logger.exception("Could not read confidence model input categories")
        raise ModelUnavailableError("The confidence model schema is not available") from exc


def load_prediction_schema(path: Path) -> PredictionSchema:
    """Return the categorical values supported by the configured model.

    Args:
        path: Configured native XGBoost JSON artifact.

    Returns:
        Model version, supported categorical values, and fixed feature values.

    Raises:
        ModelUnavailableError: If the model or its feature metadata is unusable.
    """
    return _load_prediction_schema(str(path.resolve()))


@lru_cache(maxsize=2)
def _load_booster(path_string: str) -> xgb.Booster:
    """Load one validated native XGBoost model, caching it for the process."""
    try:
        import xgboost as xgb
        from xgboost.core import XGBoostError
    except ImportError as exc:
        logger.exception("XGBoost is not installed")
        raise ModelUnavailableError("The confidence model runtime is not available") from exc

    path = Path(path_string)
    if not path.is_file():
        raise ModelUnavailableError("The confidence model artifact is not available")

    booster = xgb.Booster()
    try:
        booster.load_model(path)
    except (OSError, XGBoostError) as exc:
        logger.exception("Could not load confidence model artifact")
        raise ModelUnavailableError("The confidence model artifact is not usable") from exc

    if tuple(booster.feature_names or ()) != FEATURE_NAMES:
        raise ModelUnavailableError("The confidence model has an incompatible feature schema")
    if tuple(booster.feature_types or ()) != FEATURE_TYPES:
        raise ModelUnavailableError("The confidence model has incompatible feature types")
    return booster


def predict_confidence(
    prediction: PredictionRequest,
    model_path: Path,
    report: ConfidenceModelReport,
    schema: PredictionSchema,
) -> dict[str, object]:
    """Run a single-row inference and map raw VIIRS classes to normalized labels.

    Args:
        prediction: Validated variable form fields.
        model_path: Configured native XGBoost JSON artifact.
        report: Validated report supplying the model's output class order.
        schema: Model-defined categorical values and fixed feature values.

    Returns:
        The predicted normalized label and its three class probabilities.

    Raises:
        ModelUnavailableError: If the model or its runtime cannot produce output.
    """
    try:
        import pandas as pd
        import xgboost as xgb
        from xgboost.core import XGBoostError
    except ImportError as exc:
        logger.exception("The model prediction dependencies are not installed")
        raise ModelUnavailableError("The confidence model runtime is not available") from exc

    values: dict[str, object] = prediction.model_dump()
    values["acq_date"] = prediction.acq_date.isoformat()
    values["frp"] = float("nan") if prediction.frp is None else prediction.frp
    values.update(schema["fixed_values"])
    frame = pd.DataFrame([{name: values[name] for name in FEATURE_NAMES}])
    for name in CATEGORICAL_FEATURES:
        frame[name] = frame[name].astype("category")

    try:
        matrix = xgb.DMatrix(
            frame,
            enable_categorical=True,
            feature_names=list(FEATURE_NAMES),
            feature_types=list(FEATURE_TYPES),
        )
        booster = _load_booster(str(model_path.resolve()))
        with _MODEL_LOCK:
            output = booster.predict(matrix)
    except ModelUnavailableError:
        raise
    except (TypeError, ValueError, XGBoostError) as exc:
        logger.exception("Confidence inference failed")
        raise ModelUnavailableError("The confidence model could not process this input") from exc

    if output.shape != (1, len(report.classes)):
        raise ModelUnavailableError("The confidence model returned an incompatible output")

    raw_probabilities = output[0].tolist()
    probabilities = {
        RAW_TO_CONFIDENCE[raw_class]: float(raw_probabilities[index])
        for index, raw_class in enumerate(report.classes)
    }
    predicted_raw = report.classes[int(output[0].argmax())]
    return {
        "predicted_class": RAW_TO_CONFIDENCE[predicted_raw],
        "raw_class": predicted_raw,
        "probabilities": probabilities,
        "model_version": MODEL_VERSION,
    }
