import httpx
import pytest

from chess4f import sources


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url):
        if "/games/" in url:
            return FakeResponse(200, {"games": []})
        return FakeResponse(404 if "missing" in url else 200, {})


def test_empty_month_for_existing_user_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(sources.httpx, "Client", FakeClient)
    path, url = sources.chesscom_archive(tmp_path, "present", "2026-09", allow_empty=True)
    assert path is None and url.endswith("/2026/09")


def test_misspelled_username_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(sources.httpx, "Client", FakeClient)
    with pytest.raises(ValueError, match="not found"):
        sources.chesscom_archive(tmp_path, "missing", "2026-09", allow_empty=True)
