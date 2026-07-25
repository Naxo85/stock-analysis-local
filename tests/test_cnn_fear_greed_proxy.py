import importlib
import sys
from pathlib import Path

import pytest
from flask import Flask


MODULE_DIR = (
    Path(__file__).resolve().parents[1]
    / "gcp_functions"
    / "support_resistance_values"
)
sys.path.insert(0, str(MODULE_DIR))
proxy = importlib.import_module("main")


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clear_proxy_cache():
    proxy._CNN_FEAR_GREED_CACHE["payload"] = None
    proxy._CNN_FEAR_GREED_CACHE["expires_at"] = 0.0


def test_cnn_proxy_returns_score_and_reuses_cache(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(
            {
                "fear_and_greed": {
                    "score": 39.6,
                    "rating": "fear",
                    "timestamp": "2026-07-23T22:11:34+00:00",
                }
            }
        )

    monkeypatch.setattr(proxy.requests, "get", fake_get)
    app = Flask(__name__)

    with app.test_request_context("/market/fear-greed/cnn"):
        first_response, first_status = proxy._cnn_fear_greed_response()
        second_response, second_status = proxy._cnn_fear_greed_response()

    assert first_status == 200
    assert first_response.get_json()["score"] == pytest.approx(39.6)
    assert first_response.get_json()["cache_status"] == "miss"
    assert second_status == 200
    assert second_response.get_json()["cache_status"] == "hit"
    assert len(calls) == 1
    assert calls[0][0] == proxy._CNN_FEAR_GREED_URL
    assert calls[0][1]["headers"]["Referer"].endswith("/fear-and-greed")


def test_cnn_proxy_rejects_invalid_score(monkeypatch):
    monkeypatch.setattr(
        proxy.requests,
        "get",
        lambda *args, **kwargs: _Response(
            {"fear_and_greed": {"score": 120, "rating": "invalid"}}
        ),
    )
    app = Flask(__name__)

    with app.test_request_context("/market/fear-greed/cnn"):
        response, status = proxy._cnn_fear_greed_response()

    assert status == 502
    assert response.get_json()["error"] == "CNN Fear & Greed unavailable"
