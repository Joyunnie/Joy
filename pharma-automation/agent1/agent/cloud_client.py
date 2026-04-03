from __future__ import annotations

import logging
import os

import requests

from agent1.agent.config import AgentConfig

logger = logging.getLogger("agent1.cloud_client")


class CloudClient:
    def __init__(self, config: AgentConfig):
        self.base_url = config.agent.cloud_api_url.rstrip("/")
        self.api_key = os.environ.get("PHARMA_API_KEY", "")
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = self.api_key
        self.timeout = 30

    def post_sync(self, sync_type: str, data: dict) -> dict:
        """POST /api/v1/sync/{sync_type}. Raises ConnectionError on failure."""
        url = f"{self.base_url}/api/v1/sync/{sync_type}"
        try:
            resp = self.session.post(url, json=data, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError as e:
            logger.error("Connection failed for %s: %s", url, e)
            raise ConnectionError(str(e)) from e
        except requests.HTTPError as e:
            logger.error("HTTP error for %s: %s", url, e)
            raise

    def get_alerts(self, pharmacy_id: int, **params) -> dict:
        """GET /api/v1/alerts"""
        url = f"{self.base_url}/api/v1/alerts"
        params["pharmacy_id"] = pharmacy_id
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_inventory_status(self, pharmacy_id: int, **params) -> dict:
        """GET /api/v1/inventory/status"""
        url = f"{self.base_url}/api/v1/inventory/status"
        params["pharmacy_id"] = pharmacy_id
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_predictions(self, pharmacy_id: int, **params) -> dict:
        """GET /api/v1/predictions"""
        url = f"{self.base_url}/api/v1/predictions"
        params["pharmacy_id"] = pharmacy_id
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # --- RPA Commands ---

    def get_pending_rpa_commands(self) -> list[dict]:
        """GET /api/v1/rpa-commands/pending — Agent1 폴링."""
        url = f"{self.base_url}/api/v1/rpa-commands/pending"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("commands", [])
        except requests.ConnectionError as e:
            logger.warning("RPA poll failed (connection): %s", e)
            return []
        except requests.HTTPError as e:
            logger.error("RPA poll failed (HTTP): %s", e)
            return []

    def update_rpa_command_status(
        self, command_id: int, status: str, error_message: str | None = None
    ) -> dict | None:
        """PATCH /api/v1/rpa-commands/{id}/status"""
        url = f"{self.base_url}/api/v1/rpa-commands/{command_id}/status"
        body: dict = {"status": status}
        if error_message:
            body["error_message"] = error_message
        try:
            resp = self.session.patch(url, json=body, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.HTTPError) as e:
            logger.error("RPA status update failed for %d: %s", command_id, e)
            return None
