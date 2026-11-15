"""Confidence-model inference and performance-report endpoints."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request
from pydantic import ValidationError

from app.errors import InvalidParameterError
from app.model import (
    MODEL_VERSION,
    ConfidenceModelReport,
    PredictionRequest,
    load_prediction_schema,
    load_report,
    predict_confidence,
)
from app.schemas import first_error

bp = Blueprint("model", __name__, url_prefix="/api/v1/model")


def _report() -> ConfidenceModelReport:
    """Load the configured evaluation report for this request."""
    settings = current_app.config["SETTINGS"]
    return load_report(settings.confidence_report_path)


@bp.get("/metrics")
def metrics() -> Response:
    """Return the evaluation metrics and visualizations' source data."""
    report = _report()
    body = report.model_dump(by_alias=True)
    body["model_version"] = MODEL_VERSION
    return jsonify(body)


@bp.get("/schema")
def schema() -> Response:
    """Return the model's accepted categorical values and fixed inputs."""
    settings = current_app.config["SETTINGS"]
    return jsonify(load_prediction_schema(settings.confidence_model_path))


@bp.post("/predict")
def predict() -> Response:
    """Predict normalized confidence for one set of VIIRS feature values."""
    try:
        prediction = PredictionRequest.model_validate(request.get_json())
    except ValidationError as exc:
        raise first_error(exc) from None

    settings = current_app.config["SETTINGS"]
    options = load_prediction_schema(settings.confidence_model_path)
    if prediction.acq_date.isoformat() not in options["categories"]["acq_date"]:
        raise InvalidParameterError(
            "acq_date", "Invalid value for 'acq_date': this date is not supported by the model"
        )
    if prediction.acq_time not in options["categories"]["acq_time"]:
        raise InvalidParameterError(
            "acq_time", "Invalid value for 'acq_time': this time is not supported by the model"
        )
    result = predict_confidence(
        prediction,
        settings.confidence_model_path,
        _report(),
        options,
    )
    return jsonify(result)
