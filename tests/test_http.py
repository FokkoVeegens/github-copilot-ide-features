"""Tests for scripts/common/http.py"""
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

import scripts.common.http as http_module
from scripts.common.http import get_session, _build_session


class TestBuildSession:
    def test_returns_requests_session(self):
        session = _build_session()
        assert isinstance(session, requests.Session)

    def test_user_agent_header_set(self):
        session = _build_session()
        assert "User-Agent" in session.headers
        assert "github-copilot-ide-features" in session.headers["User-Agent"]

    def test_github_token_sets_authorization_header(self):
        session = _build_session(github_token="test-token-123")
        assert session.headers.get("Authorization") == "Bearer test-token-123"

    def test_no_token_no_authorization_header(self):
        # Ensure GITHUB_TOKEN env var is absent for this test
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            session = _build_session()
        assert "Authorization" not in session.headers

    def test_env_github_token_sets_authorization_header(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token-456"}):
            session = _build_session()
        assert session.headers.get("Authorization") == "Bearer env-token-456"


class TestGetSession:
    def setup_method(self):
        # Reset the module-level singleton before each test
        http_module._state["session"] = None

    def teardown_method(self):
        http_module._state["session"] = None

    def test_returns_session_instance(self):
        session = get_session()
        assert isinstance(session, requests.Session)

    def test_returns_same_instance_on_second_call(self):
        s1 = get_session()
        s2 = get_session()
        assert s1 is s2

    def test_reuses_existing_session(self):
        existing = MagicMock(spec=requests.Session)
        http_module._state["session"] = existing
        result = get_session()
        assert result is existing
