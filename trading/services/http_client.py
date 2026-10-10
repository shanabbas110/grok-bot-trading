"""HTTP helpers with retries and rate-limit backoff."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, user_agent: str = "GrokBot/1.0", max_retries: int = 4, timeout: float = 15.0):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": user_agent})
        self.max_retries = max_retries
        self.timeout = timeout

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.request(method, url, **kwargs)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                    sleep_s = retry_after if retry_after > 0 else min(32, (2 ** attempt) + random.random())
                    logger.warning("Rate limited %s — sleeping %.1fs", url, sleep_s)
                    time.sleep(sleep_s)
                    continue
                if resp.status_code >= 500:
                    sleep_s = min(16, (2 ** attempt) + random.random() * 0.5)
                    logger.warning("Server error %s on %s — retry %s", resp.status_code, url, attempt + 1)
                    time.sleep(sleep_s)
                    continue
                return resp
            except requests.RequestException as e:
                last_exc = e
                sleep_s = min(16, (2 ** attempt) + random.random() * 0.5)
                logger.warning("HTTP error %s on %s — retry %s", e, url, attempt + 1)
                time.sleep(sleep_s)
        if last_exc:
            raise last_exc
        raise requests.RequestException(f"Failed after {self.max_retries} attempts: {url}")

    def get_json(self, url: str, **kwargs) -> Any:
        resp = self.request("GET", url, **kwargs)
        if not resp.ok:
            raise requests.HTTPError(f"{resp.status_code} {resp.text[:200]}", response=resp)
        return resp.json()

    def post_json(self, url: str, **kwargs) -> Any:
        resp = self.request("POST", url, **kwargs)
        if not resp.ok:
            raise requests.HTTPError(f"{resp.status_code} {resp.text[:200]}", response=resp)
        return resp.json()
