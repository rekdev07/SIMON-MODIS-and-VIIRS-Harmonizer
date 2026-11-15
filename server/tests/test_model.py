"""Tests for the model evaluation and confidence prediction endpoints."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from flask.testing import FlaskClient

PREDICTION_INPUT = {
    "latitude": 16.1985,
    "longitude": -95.17513,
    "acq_date": "2014-01-02",
    "acq_time": "0701",
    "scan": 0.77,
    "track": 0.78,
    "daynight": "N",
    "frp": 2.77,
    "bright_t31": 287.73,
    "type": "2",
    "brightness": 303.23,
}


def test_model_metrics(client: FlaskClient) -> None:
    """Expose the report values and preserve its class order."""
    response = client.get("/api/v1/model/metrics")

    assert response.status_code == 200
    body = response.get_json()
    assert body["classes"] == ["l", "n", "h"]
    assert body["n_test"] == 37_383
    assert body["reporte"]["accuracy"] == 0.8533023031859401
    assert body["confusion_matriz"][1] == [4887, 26277, 0]
    assert body["model_version"] == "xgbrf-confidence-v1"


def test_model_schema_exposes_categories_supported_by_the_artifact(
    client: FlaskClient,
) -> None:
    """Expose the date and time categories required to construct valid inputs."""
    response = client.get("/api/v1/model/schema")

    assert response.status_code == 200
    body = response.get_json()
    assert body["categories"]["acq_date"][0] == "2014-01-02"
    assert body["categories"]["acq_date"][-1] == "2015-01-01"
    assert "0701" in body["categories"]["acq_time"]
    assert body["fixed_values"] == {
        "version": "2",
        "instrument": "SNPP",
        "satellite": "SNPP",
    }


def test_model_prediction_returns_normalized_classes_and_probabilities(
    client: FlaskClient,
) -> None:
    """Run the shipped model with the provided sample feature values."""
    response = client.post("/api/v1/model/predict", json=PREDICTION_INPUT)

    assert response.status_code == 200
    body = response.get_json()
    assert body["predicted_class"] in {"low", "nominal", "high"}
    assert body["raw_class"] in {"l", "n", "h"}
    assert set(body["probabilities"]) == {"low", "nominal", "high"}
    assert abs(sum(body["probabilities"].values()) - 1) < 1e-6
    assert body["predicted_class"] == {
        "l": "low",
        "n": "nominal",
        "h": "high",
    }[body["raw_class"]]


def test_model_prediction_accepts_missing_frp(client: FlaskClient) -> None:
    """Pass an absent FRP value through as the model's missing-value input."""
    response = client.post(
        "/api/v1/model/predict",
        json={**PREDICTION_INPUT, "frp": None},
    )

    assert response.status_code == 200


def test_prediction_rejects_unseen_categorical_dates(client: FlaskClient) -> None:
    """Return a field validation error instead of a model-runtime failure."""
    response = client.post(
        "/api/v1/model/predict",
        json={**PREDICTION_INPUT, "acq_date": "2026-11-15"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "acq_date"


def test_prediction_rejects_unseen_categorical_times(client: FlaskClient) -> None:
    """Reject acquisition times absent from the model's saved vocabulary."""
    response = client.post(
        "/api/v1/model/predict",
        json={**PREDICTION_INPUT, "acq_time": "2359"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "acq_time"


def test_prediction_rejects_confidence_as_an_input(client: FlaskClient) -> None:
    """Do not allow the target label to leak into prediction features."""
    response = client.post(
        "/api/v1/model/predict",
        json={**PREDICTION_INPUT, "confidence": "n"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "confidence"


def test_prediction_validates_feature_ranges(client: FlaskClient) -> None:
    """Reject coordinates and categorical values outside the model contract."""
    response = client.post(
        "/api/v1/model/predict",
        json={**PREDICTION_INPUT, "latitude": 91},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "latitude"


def test_prediction_reports_missing_model_artifact(
    app, client: FlaskClient, tmp_path: Path
) -> None:
    """Surface model availability failures as an explicit service error."""
    settings = app.config["SETTINGS"]
    app.config["SETTINGS"] = replace(
        settings,
        confidence_model_path=tmp_path / "missing-model.json",
    )

    response = client.post("/api/v1/model/predict", json=PREDICTION_INPUT)

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "MODEL_UNAVAILABLE"
