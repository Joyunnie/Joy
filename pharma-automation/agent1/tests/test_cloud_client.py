"""Tests for CloudClient: post_sync, GET methods, error handling.

Covers: successful responses, HTTP errors, connection errors, timeout behavior,
and response parsing for all public methods.
"""
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

from agent1.agent.cloud_client import CloudClient


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.agent.cloud_api_url = "http://test-cloud:8000"
    return config


@pytest.fixture
def client(mock_config):
    with patch.dict("os.environ", {"PHARMA_API_KEY": "test-key-123"}):
        c = CloudClient(mock_config)
    return c


class TestPostSync:
    """post_sync() — the critical sync path."""

    def test_success(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"synced_count": 5}
        mock_resp.raise_for_status.return_value = None
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.post_sync("inventory", {"items": []})
        assert result == {"synced_count": 5}
        client.session.post.assert_called_once()
        call_args = client.session.post.call_args
        assert "/api/v1/sync/inventory" in call_args.args[0]

    def test_connection_error_raises(self, client):
        client.session.post = MagicMock(
            side_effect=requests.ConnectionError("connection refused")
        )
        with pytest.raises(ConnectionError):
            client.post_sync("inventory", {"items": []})

    def test_http_error_raises(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        client.session.post = MagicMock(return_value=mock_resp)

        with pytest.raises(requests.HTTPError):
            client.post_sync("inventory", {"items": []})


class TestGetAlerts:
    """get_alerts() — unprotected GET (no try/catch in implementation)."""

    def test_success(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"alerts": [], "total": 0}
        mock_resp.raise_for_status.return_value = None
        client.session.get = MagicMock(return_value=mock_resp)

        result = client.get_alerts(pharmacy_id=1)
        assert result == {"alerts": [], "total": 0}

    def test_passes_params(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        client.session.get = MagicMock(return_value=mock_resp)

        client.get_alerts(pharmacy_id=42, unread_only=True)
        call_kwargs = client.session.get.call_args.kwargs
        assert call_kwargs["params"]["pharmacy_id"] == 42
        assert call_kwargs["params"]["unread_only"] is True

    def test_http_error_propagates(self, client):
        """HTTPError is not caught — propagates to caller."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        client.session.get = MagicMock(return_value=mock_resp)

        with pytest.raises(requests.HTTPError):
            client.get_alerts(pharmacy_id=1)


class TestGetInventoryStatus:
    def test_success(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"items": []}
        mock_resp.raise_for_status.return_value = None
        client.session.get = MagicMock(return_value=mock_resp)

        result = client.get_inventory_status(pharmacy_id=1)
        assert result == {"items": []}

    def test_connection_error_propagates(self, client):
        client.session.get = MagicMock(
            side_effect=requests.ConnectionError("timeout")
        )
        with pytest.raises(requests.ConnectionError):
            client.get_inventory_status(pharmacy_id=1)


class TestGetPredictions:
    def test_success(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"predictions": []}
        mock_resp.raise_for_status.return_value = None
        client.session.get = MagicMock(return_value=mock_resp)

        result = client.get_predictions(pharmacy_id=1)
        assert result == {"predictions": []}


class TestClientInit:
    """Constructor behavior."""

    def test_api_key_from_env(self, mock_config):
        with patch.dict("os.environ", {"PHARMA_API_KEY": "my-secret-key"}):
            c = CloudClient(mock_config)
        assert c.api_key == "my-secret-key"
        assert c.session.headers["X-API-Key"] == "my-secret-key"

    def test_missing_api_key_defaults_to_empty(self, mock_config):
        with patch.dict("os.environ", {}, clear=True):
            c = CloudClient(mock_config)
        assert c.api_key == ""

    def test_base_url_strips_trailing_slash(self, mock_config):
        mock_config.agent.cloud_api_url = "http://host:8000/"
        c = CloudClient(mock_config)
        assert c.base_url == "http://host:8000"
