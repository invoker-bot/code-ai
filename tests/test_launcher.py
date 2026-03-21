import os
import pytest
from unittest.mock import patch, MagicMock
from src.code_ai.models import ApiProfile, LoginProfile
from src.code_ai.launcher import prepare_environment


def test_prepare_env_api_mode():
    """Test environment preparation for API mode"""
    profile = ApiProfile(
        name="test-api",
        type="claude",
        base_url="https://api.anthropic.com",
        token="sk-ant-test"
    )

    env = prepare_environment(profile)

    assert env["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-ant-test"


def test_prepare_env_login_mode():
    """Test environment preparation for login mode"""
    profile = LoginProfile(
        name="test-login",
        type="claude",
        credentials_path="~/.claude-profiles/account-a"
    )

    env = prepare_environment(profile)

    # Should NOT have API environment variables
    assert "ANTHROPIC_BASE_URL" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    # Should have CLAUDE_CONFIG_DIR with expanded path
    expected_path = os.path.expanduser("~/.claude-profiles/account-a")
    assert env["CLAUDE_CONFIG_DIR"] == expected_path


def test_prepare_env_with_proxy():
    """Test environment preparation with proxy"""
    profile = ApiProfile(
        name="test-proxy",
        type="gemini",
        base_url="https://generativelanguage.googleapis.com",
        api_key="AIza-test",
        proxy="http://127.0.0.1:7890"
    )

    env = prepare_environment(profile)

    assert env["HTTP_PROXY"] == "http://127.0.0.1:7890"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:7890"


def test_prepare_env_login_clears_api_vars():
    """Test that login mode clears API environment variables"""
    # Set up environment with existing API variables
    with patch.dict(os.environ, {
        "ANTHROPIC_BASE_URL": "https://old.url",
        "ANTHROPIC_AUTH_TOKEN": "old-token"
    }):
        profile = LoginProfile(
            name="test-login",
            type="claude",
            credentials_path="~/.claude-profiles/account-a"
        )

        env = prepare_environment(profile)

        # Should be cleared
        assert "ANTHROPIC_BASE_URL" not in env
        assert "ANTHROPIC_AUTH_TOKEN" not in env


def test_prepare_env_codex_api_mode():
    """Test environment preparation for codex API mode"""
    profile = ApiProfile(
        name="test-codex-api",
        type="codex",
        base_url="https://api.openai.com/v1",
        api_key="sk-test"
    )

    env = prepare_environment(profile)

    # Should only have OPENAI_API_KEY, not OPENAI_BASE_URL
    assert env["OPENAI_API_KEY"] == "sk-test"
    assert "OPENAI_BASE_URL" not in env


def test_prepare_env_codex_login_mode():
    """Test environment preparation for codex login mode"""
    profile = LoginProfile(
        name="test-codex-login",
        type="codex",
        credentials_path="~/.codex-profiles/account-a"
    )

    env = prepare_environment(profile)

    # Should NOT have API environment variables
    assert "OPENAI_API_KEY" not in env
    # Should have CODEX_CONFIG_DIR with expanded path
    expected_path = os.path.expanduser("~/.codex-profiles/account-a")
    assert env["CODEX_CONFIG_DIR"] == expected_path
