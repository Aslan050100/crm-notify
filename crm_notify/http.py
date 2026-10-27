"""HTTP-клиент с повторами при 429/5xx и ограничением частоты запросов."""

from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


class Http:
    def __init__(self, base_url: str, headers: dict[str, str], min_interval: float = 0.15, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(headers)
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0

    def request(self, method: str, path: str, *, ok_empty: bool = False, **kwargs):
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(5):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                if attempt == 4:
                    raise ApiError(f"Нет связи с {url}: {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                delay = float(resp.headers.get("Retry-After") or 2 ** attempt)
                log.warning("%s %s → %s, повтор через %.0f с", method, url, resp.status_code, delay)
                time.sleep(delay)
                continue
            if resp.status_code == 204:
                return None
            if resp.status_code >= 400:
                raise ApiError(
                    f"{method} {url} → HTTP {resp.status_code}: {resp.text[:300]}",
                    status=resp.status_code,
                    body=resp.text,
                )
            if not resp.content:
                return None
            return resp.json()
        raise ApiError(f"{method} {url}: сервер не отвечает после повторов")

    def get(self, path: str, **kw):
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw):
        return self.request("POST", path, **kw)

    def patch(self, path: str, **kw):
        return self.request("PATCH", path, **kw)
