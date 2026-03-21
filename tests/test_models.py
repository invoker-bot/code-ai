import pytest
from src.code_ai.models import (
    ApiProfile, LoginProfile, profile_from_dict, profile_to_dict, VALID_TYPES
)

def test_api_profile_creation():
    """Test creating an API profile"""
    profile = ApiProfile(
        name="test-api",
        type="claude",
        base_url="https://api.anthropic.com",
        token="sk-ant-test"
    )
    assert profile.name == "test-api"
    assert profile.type == "claude"
    assert profile.base_url == "https://api.anthropic.com"
    assert profile.token == "sk-ant-test"
    assert profile.proxy is None

def test_login_profile_creation():
    """Test creating a login profile"""
    profile = LoginProfile(
        name="test-login",
        type="claude",
        credentials_path="~/.claude-profiles/account-a"
    )
    assert profile.name == "test-login"
    assert profile.type == "claude"
    assert profile.credentials_path == "~/.claude-profiles/account-a"
    assert profile.proxy is None

def test_profile_with_proxy():
    """Test profile with proxy"""
    profile = ApiProfile(
        name="test-proxy",
        type="gemini",
        base_url="https://generativelanguage.googleapis.com",
        api_key="AIza-test",
        proxy="http://127.0.0.1:7890"
    )
    assert profile.proxy == "http://127.0.0.1:7890"

def test_profile_from_dict_api_mode():
    """Test converting dict to API profile"""
    data = {
        "name": "my-api",
        "type": "claude",
        "mode": "api",
        "base_url": "https://api.anthropic.com",
        "token": "sk-ant-test",
        "proxy": None
    }
    profile = profile_from_dict(data)
    assert isinstance(profile, ApiProfile)
    assert profile.name == "my-api"
    assert profile.base_url == "https://api.anthropic.com"

def test_profile_from_dict_login_mode():
    """Test converting dict to login profile"""
    data = {
        "name": "my-login",
        "type": "claude",
        "mode": "login",
        "credentials_path": "~/.claude-profiles/account-a",
        "proxy": "http://127.0.0.1:7890"
    }
    profile = profile_from_dict(data)
    assert isinstance(profile, LoginProfile)
    assert profile.credentials_path == "~/.claude-profiles/account-a"
    assert profile.proxy == "http://127.0.0.1:7890"

def test_profile_from_dict_defaults_to_api():
    """Test that missing mode defaults to api"""
    data = {
        "name": "legacy",
        "type": "claude",
        "base_url": "https://api.anthropic.com",
        "token": "sk-ant-test"
    }
    profile = profile_from_dict(data)
    assert isinstance(profile, ApiProfile)

def test_profile_to_dict_api():
    """Test converting API profile to dict"""
    profile = ApiProfile(
        name="my-api",
        type="claude",
        base_url="https://api.anthropic.com",
        token="sk-ant-test"
    )
    data = profile_to_dict(profile)
    assert data["name"] == "my-api"
    assert data["type"] == "claude"
    assert data["mode"] == "api"
    assert data["base_url"] == "https://api.anthropic.com"
    assert data["token"] == "sk-ant-test"

def test_profile_to_dict_login():
    """Test converting login profile to dict"""
    profile = LoginProfile(
        name="my-login",
        type="claude",
        credentials_path="~/.claude-profiles/account-a",
        proxy="http://127.0.0.1:7890"
    )
    data = profile_to_dict(profile)
    assert data["name"] == "my-login"
    assert data["type"] == "claude"
    assert data["mode"] == "login"
    assert data["credentials_path"] == "~/.claude-profiles/account-a"
    assert data["proxy"] == "http://127.0.0.1:7890"

def test_valid_types():
    """Test VALID_TYPES constant"""
    assert VALID_TYPES == ("claude", "gemini", "codex")
