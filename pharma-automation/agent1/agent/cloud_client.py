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
