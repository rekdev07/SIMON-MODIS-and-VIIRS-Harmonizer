"""Tests for LAN access: host default, private-network CORS and startup URLs."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import create_app
from app.config import load_settings
from app.network import PRIVATE_NETWORK_ORIGIN, get_lan_ip
from run import startup_urls
from tests.conftest import make_settings

HOTSPOTS_QUERY = {"lat1": 18, "lon1": -100, "lat2": 20, "lon2": -98,
                  "start_date": "2024-04-15", "end_date": "2024-04-20"}


@pytest.mark.parametrize("origin", [
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://192.168.1.23:5173",
    "http://10.0.0.5",
    "https://172.16.0.1:8443",
    "http://172.31.255.255:5173",
    "http://my-laptop.local:5173",
])
def test_private_origins_match(origin: str) -> None:
    assert PRIVATE_NETWORK_ORIGIN.match(origin)


@pytest.mark.parametrize("origin", [
    "https://example.com",
    "http://8.8.8.8",
    "http://172.32.0.1:5173",          # just outside 172.16.0.0/12
    "http://192.169.1.1",
    "http://192.168.1.23.evil.com",    # private IP as a prefix of a public domain
    "http://192.168.1.256",            # not a valid octet
    "ftp://192.168.1.23",
])
def test_public_or_invalid_origins_do_not_match(origin: str) -> None:
    assert not PRIVATE_NETWORK_ORIGIN.match(origin)


def _cors_header(db_path: Path, origin: str, **overrides) -> str | None:
    app = create_app(make_settings(db_path, **overrides))
    try:
        response = app.test_client().get("/api/v1/hotspots", query_string=HOTSPOTS_QUERY,
                                         headers={"Origin": origin})
        assert response.status_code == 200
        return response.headers.get("Access-Control-Allow-Origin")
    finally:
        app.extensions["hotspots_db"].close()


def test_cors_allows_lan_origin_when_enabled(db_path: Path) -> None:
    origin = "http://192.168.1.23:5173"
    assert _cors_header(db_path, origin, cors_allow_lan=True) == origin


def test_cors_blocks_public_origin_even_with_lan_enabled(db_path: Path) -> None:
    assert _cors_header(db_path, "https://example.com", cors_allow_lan=True) is None


def test_cors_blocks_lan_origin_when_disabled(db_path: Path) -> None:
    assert _cors_header(db_path, "http://192.168.1.23:5173", cors_allow_lan=False) is None


def test_cors_wildcard_allows_any_origin(db_path: Path) -> None:
    # flask-cors echoes the caller's origin back (equivalent to "*" for the browser).
    assert _cors_header(db_path, "https://example.com", cors_origins=["*"]) == "https://example.com"


def test_load_settings_defaults_to_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_HOST", raising=False)
    monkeypatch.delenv("CORS_ALLOW_LAN", raising=False)
    monkeypatch.setattr("app.config.load_dotenv", lambda *args, **kwargs: False)
    settings = load_settings()
    assert settings.host == "0.0.0.0"
    assert settings.cors_allow_lan is True


def test_load_settings_local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("CORS_ALLOW_LAN", "0")
    monkeypatch.setattr("app.config.load_dotenv", lambda *args, **kwargs: False)
    settings = load_settings()
    assert settings.host == "127.0.0.1"
    assert settings.cors_allow_lan is False


def test_startup_urls_show_lan_address(db_path: Path) -> None:
    lines = startup_urls(make_settings(db_path, host="0.0.0.0", port=5000), "192.168.1.23")
    assert lines[0] == "Local:   http://localhost:5000"
    assert lines[1].startswith("Network: http://192.168.1.23:5000")


def test_startup_urls_without_network(db_path: Path) -> None:
    lines = startup_urls(make_settings(db_path, host="0.0.0.0", port=5000), None)
    assert "no LAN connection" in lines[1]


def test_startup_urls_local_only_hint(db_path: Path) -> None:
    lines = startup_urls(make_settings(db_path, host="127.0.0.1", port=5001), "192.168.1.23")
    assert lines[0] == "Local:   http://127.0.0.1:5001"
    assert "API_HOST=0.0.0.0" in lines[1]


def test_get_lan_ip_is_private_or_none() -> None:
    ip = get_lan_ip()
    assert ip is None or not ip.startswith("127.")
