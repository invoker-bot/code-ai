from src.code_ai.cli import UPGRADE_PACKAGES


def test_upgrade_packages_use_official_grok_cli_instead_of_gemini():
    assert "@xai-official/grok" in UPGRADE_PACKAGES
    assert "@google/gemini-cli" not in UPGRADE_PACKAGES
