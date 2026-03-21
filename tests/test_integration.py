import pytest
from unittest.mock import patch, MagicMock
from src.code_ai.config import load_config, save_config
from src.code_ai.profiles import add_profile, list_profiles, show_profile, remove_profile
from src.code_ai.models import profile_from_dict, ApiProfile, LoginProfile
from src.code_ai.launcher import prepare_environment


class TestFullWorkflowApiProfile:
    """Test complete workflow for API profile (Claude)"""

    def test_full_workflow_api_profile(self, monkeypatch, tmp_path):
        """Test full workflow: add API profile -> show -> list -> remove"""
        # Mock config file location
        config_file = tmp_path / "config.yaml"

        with patch("src.code_ai.config.CONFIG_FILE", config_file):
            # Step 1: Initialize config
            config = {"profiles": {}}
            save_config(config)

            # Step 2: Add API profile interactively
            inputs = [
                "my-claude-api",           # Profile name
                "claude",                  # Type
                "api",                     # Mode
                "https://api.anthropic.com",  # Base URL
                "sk-ant-test-token",       # Auth token
                "",                        # No proxy
            ]

            with patch("builtins.input", side_effect=inputs):
                config = load_config()
                config = add_profile(config)
                save_config(config)

            # Step 3: Verify profile was added
            config = load_config()
            assert "my-claude-api" in config["profiles"]
            profile_dict = config["profiles"]["my-claude-api"]
            assert profile_dict["type"] == "claude"
            assert profile_dict["mode"] == "api"
            assert profile_dict["base_url"] == "https://api.anthropic.com"
            assert profile_dict["token"] == "sk-ant-test-token"

            # Step 4: Convert to profile object and verify
            profile = profile_from_dict(profile_dict)
            assert isinstance(profile, ApiProfile)
            assert profile.type == "claude"

            # Step 5: Test environment preparation
            env = prepare_environment(profile)
            assert env["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com"
            assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-ant-test-token"

            # Step 6: Show profile
            with patch("builtins.print") as mock_print:
                show_profile(config, "my-claude-api")
                # Verify show_profile was called and printed something
                assert mock_print.called

            # Step 7: List profiles
            with patch("builtins.print") as mock_print:
                list_profiles(config)
                # Verify list_profiles was called and printed something
                assert mock_print.called

            # Step 8: Remove profile
            config = remove_profile(config, "my-claude-api")
            assert "my-claude-api" not in config["profiles"]


class TestFullWorkflowLoginProfile:
    """Test complete workflow for login profile (Claude)"""

    def test_full_workflow_login_profile(self, monkeypatch, tmp_path):
        """Test full workflow: add login profile -> show -> list -> remove"""
        # Mock config file location
        config_file = tmp_path / "config.yaml"

        with patch("src.code_ai.config.CONFIG_FILE", config_file):
            # Step 1: Initialize config
            config = {"profiles": {}}
            save_config(config)

            # Step 2: Add login profile interactively
            inputs = [
                "my-claude-login",         # Profile name
                "claude",                  # Type
                "login",                   # Mode
                "~/.claude-profiles/account-a",  # Credentials path
                "http://127.0.0.1:7890",   # Proxy
            ]

            with patch("builtins.input", side_effect=inputs):
                config = load_config()
                config = add_profile(config)
                save_config(config)

            # Step 3: Verify profile was added
            config = load_config()
            assert "my-claude-login" in config["profiles"]
            profile_dict = config["profiles"]["my-claude-login"]
            assert profile_dict["type"] == "claude"
            assert profile_dict["mode"] == "login"
            assert profile_dict["credentials_path"] == "~/.claude-profiles/account-a"
            assert profile_dict["proxy"] == "http://127.0.0.1:7890"

            # Step 4: Convert to profile object and verify
            profile = profile_from_dict(profile_dict)
            assert isinstance(profile, LoginProfile)
            assert profile.type == "claude"

            # Step 5: Test environment preparation
            env = prepare_environment(profile)
            # Login mode should NOT have API environment variables
            assert "ANTHROPIC_BASE_URL" not in env
            assert "ANTHROPIC_AUTH_TOKEN" not in env
            # Should have CLAUDE_CONFIG_DIR with expanded path
            import os
            expected_path = os.path.expanduser("~/.claude-profiles/account-a")
            assert env["CLAUDE_CONFIG_DIR"] == expected_path
            # Should have proxy
            assert env["HTTP_PROXY"] == "http://127.0.0.1:7890"
            assert env["HTTPS_PROXY"] == "http://127.0.0.1:7890"

            # Step 6: Show profile
            with patch("builtins.print") as mock_print:
                show_profile(config, "my-claude-login")
                # Verify show_profile was called and printed something
                assert mock_print.called

            # Step 7: List profiles
            with patch("builtins.print") as mock_print:
                list_profiles(config)
                # Verify list_profiles was called and printed something
                assert mock_print.called

            # Step 8: Remove profile
            config = remove_profile(config, "my-claude-login")
            assert "my-claude-login" not in config["profiles"]


class TestBackwardCompatibility:
    """Test backward compatibility with legacy profiles"""

    def test_backward_compatibility(self, tmp_path):
        """Test that legacy profiles (without mode field) still work"""
        # Mock config file location
        config_file = tmp_path / "config.yaml"

        with patch("src.code_ai.config.CONFIG_FILE", config_file):
            # Step 1: Create a legacy profile (without mode field)
            legacy_config = {
                "profiles": {
                    "legacy-claude": {
                        "name": "legacy-claude",
                        "type": "claude",
                        "base_url": "https://api.anthropic.com",
                        "token": "sk-ant-legacy-token"
                        # Note: no "mode" field
                    }
                }
            }
            save_config(legacy_config)

            # Step 2: Load config and verify it works
            config = load_config()
            assert "legacy-claude" in config["profiles"]
            profile_dict = config["profiles"]["legacy-claude"]

            # Step 3: Convert to profile object
            # Should default to API mode
            profile = profile_from_dict(profile_dict)
            assert isinstance(profile, ApiProfile)
            assert profile.base_url == "https://api.anthropic.com"
            assert profile.token == "sk-ant-legacy-token"

            # Step 4: Test environment preparation
            env = prepare_environment(profile)
            assert env["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com"
            assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-ant-legacy-token"

            # Step 5: Show profile should work
            with patch("builtins.print") as mock_print:
                show_profile(config, "legacy-claude")
                assert mock_print.called

            # Step 6: List profiles should work
            with patch("builtins.print") as mock_print:
                list_profiles(config)
                assert mock_print.called

            # Step 7: Test with other profile types (gemini, codex)
            gemini_config = {
                "profiles": {
                    "legacy-gemini": {
                        "name": "legacy-gemini",
                        "type": "gemini",
                        "base_url": "https://generativelanguage.googleapis.com",
                        "api_key": "AIza-test-key"
                        # Note: no "mode" field
                    }
                }
            }
            save_config(gemini_config)

            config = load_config()
            profile_dict = config["profiles"]["legacy-gemini"]
            profile = profile_from_dict(profile_dict)

            # Should default to API mode
            assert isinstance(profile, ApiProfile)
            assert profile.type == "gemini"
            assert profile.api_key == "AIza-test-key"

            # Test environment preparation
            env = prepare_environment(profile)
            assert env["GOOGLE_GEMINI_BASE_URL"] == "https://generativelanguage.googleapis.com"
            assert env["GEMINI_API_KEY"] == "AIza-test-key"
