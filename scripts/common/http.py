"""Shared HTTP client with retries, user-agent, and optional GitHub token."""
import os
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_USER_AGENT = "github-copilot-ide-features-scraper/1.0 (https://github.com)"
_DEFAULT_TIMEOUT = 30  # seconds


def _build_session(github_token: str | None = None) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({"User-Agent": _USER_AGENT})
    token = github_token or os.getenv("GITHUB_TOKEN")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _build_session_no_auth() -> requests.Session:
    """Build a session without any Authorization header (for non-GitHub APIs)."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


# Module-level singleton; recreate when token env changes across tests.
_state: dict = {"session": None, "session_no_auth": None}


def get_session(github_token: str | None = None) -> requests.Session:
    """Return (or create) the shared requests.Session."""
    if _state["session"] is None:
        _state["session"] = _build_session(github_token)
    return _state["session"]


def get_session_no_auth() -> requests.Session:
    """Return (or create) a shared requests.Session without Authorization headers."""
    if _state["session_no_auth"] is None:
        _state["session_no_auth"] = _build_session_no_auth()
    return _state["session_no_auth"]


def get_json(
    url: str,
    *,
    params: dict | None = None,
    github_token: str | None = None,
    use_auth: bool = True,
) -> object:
    """GET *url* and return the decoded JSON, respecting GitHub rate-limit headers.

    Pass ``use_auth=False`` for third-party APIs that must not receive the
    GitHub token in the Authorization header.
    """
    session = get_session(github_token) if use_auth else get_session_no_auth()
    response = session.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
    _handle_rate_limit(response)
    response.raise_for_status()
    return response.json()


def get_text(
    url: str,
    *,
    params: dict | None = None,
    use_auth: bool = True,
    encoding: str | None = None,
) -> str:
    """GET *url* and return the response body as text.

    Pass ``use_auth=False`` for third-party APIs that must not receive the
    GitHub token in the Authorization header.
    """
    session = get_session() if use_auth else get_session_no_auth()
    response = session.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
    response.raise_for_status()
    if encoding is not None:
        return response.content.decode(encoding)
    return response.text


def _handle_rate_limit(response: requests.Response) -> None:
    """If a 429 response slips through the retry adapter, sleep and let the caller retry."""
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", "60"))
        time.sleep(retry_after)
