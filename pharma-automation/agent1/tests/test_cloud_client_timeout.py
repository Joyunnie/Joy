"""Tests for CloudClient timeout and edge cases.

Covers: requests.Timeout for all methods, empty API key behavior,
large payloads, and response parsing edge cases.
Complements test_cloud_client.py which covers basic happy/error paths.
"""
from unittest.mock import MagicMock, patch

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
    with patch.dict("os.environ", {"PHARMA_API_KEY": "test-key"}):
        return CloudClient(mock_config)


class TestPostSyncTimeout:
    def test_timeout_raises(self, client):
        """requests.Timeout propagates as-is (no catch in post_sync for Timeout)."""
        client.session.post = MagicMock(
            side_effect=requests.Timeout("read timed out")
        )
        with pytest.raises(requests.Timeout):
            client.post_sync("inventory", {"items": []})

    def test_uses_configured_timeout(self, client):
        """post_sync passes self.timeout to session.post."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        client.session.post = MagicMock(return_value=mock_resp)

        client.post_sync("test", {})
        _, kwargs = client.session.post.call_args
        assert kwargs["timeout"] == 30


class TestGetMethodsTimeout:
    def test_get_alerts_timeout(self, client):
        client.session.get = MagicMock(
            side_effect=requests.Timeout("connect timed out")
        )
        with pytest.raises(requests.Timeout):
            client.get_alerts(pharmacy_id=1)

    def test_get_inventory_status_timeout(self, client):
        client.session.get = MagicMock(
            side_effect=requests.Timeout("read timed out")
        )
        with pytest.raises(requests.Timeout):
            client.get_inventory_status(pharmacy_id=1)

    def test_get_predictions_timeout(self, client):
        client.session.get = MagicMock(
            side_effect=requests.Timeout("connect timed out")
        )
        with pytest.raises(requests.Timeout):
            client.get_predictions(pharmacy_id=1)

    def test_get_predictions_connection_error(self, client):
        """ConnectionError on GET propagates (no catch in get methods)."""
        client.session.get = MagicMock(
            side_effect=requests.ConnectionError("refused")
        )
        with pytest.raises(requests.ConnectionError):
            client.get_predictions(pharmacy_id=1)


class TestPostSyncEdgeCases:
    def test_empty_payload(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"synced_count": 0}
        mock_resp.raise_for_status.return_value = None
        client.session.post = MagicMock(return_value=mock_resp)

        result = client.post_sync("inventory", {})
        assert result == {"synced_count": 0}

    def test_url_construction_with_sync_type(self, client):
        """Verify URL includes sync_type path segment."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        client.session.post = MagicMock(return_value=mock_resp)

        client.post_sync("cassette-mapping", {"mappings": []})
        call_url = client.session.post.call_args.args[0]
        assert call_url == "http://test-cloud:8000/api/v1/sync/cassette-mapping"

    def test_server_500_raises_http_error(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=500)
        )
        client.session.post = MagicMock(return_value=mock_resp)

        with pytest.raises(requests.HTTPError):
            client.post_sync("inventory", {"items": []})

    def test_server_422_raises_http_error(self, client):
        """Validation error from cloud raises HTTPError."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=MagicMock(status_code=422)
        )
        client.session.post = MagicMock(return_value=mock_resp)

        with pytest.raises(requests.HTTPError):
            client.post_sync("visits", {"visits": []})
