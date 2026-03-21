import sys

from .models import VALID_TYPES, profile_from_dict


def list_profiles(config):
    from .config import save_config

    profiles = config.get("profiles", {})

    # Auto-migrate old profiles without mode field
    migrated = False
    for name, p in profiles.items():
        if "mode" not in p:
            p["mode"] = "api"
            migrated = True

    if migrated:
        save_config(config)

    if not profiles:
        print("No profiles configured.")
        return

    print(f"{'Name':<20} {'Type':<10} {'Mode':<8} {'Base URL/Credentials':<42} {'Proxy':<20}")
    print("-" * 100)

    for name, p in profiles.items():
        profile = profile_from_dict(p)
        ptype = profile.type
        mode = p.get("mode", "api")

        # Determine what to display in the Base URL/Credentials column
        if mode == "login":
            url_or_creds = p.get("credentials_path", "")
        else:  # api mode
            url_or_creds = p.get("base_url", "")

        # Truncate long strings
        if len(url_or_creds) > 40:
            url_or_creds = url_or_creds[:37] + "..."

        # Get proxy or display "-"
        proxy_display = profile.proxy if profile.proxy else "-"
        if len(proxy_display) > 20:
            proxy_display = proxy_display[:17] + "..."

        print(f"{name:<20} {ptype:<10} {mode:<8} {url_or_creds:<42} {proxy_display:<20}")


def add_profile(config):
    name = input("Profile name: ").strip()
    if not name:
        print("Error: name cannot be empty.")
        sys.exit(1)
    if name in config.get("profiles", {}):
        print(f"Error: profile '{name}' already exists.")
        sys.exit(1)

    ptype = input(f"Type ({'/'.join(VALID_TYPES)}): ").strip().lower()
    if ptype not in VALID_TYPES:
        print(f"Error: type must be one of {VALID_TYPES}.")
        sys.exit(1)

    profile_data = {
        "type": ptype,
    }

    # Handle mode for Claude and Codex
    if ptype in ("claude", "codex"):
        mode = input("Mode (api/login) [api]: ").strip().lower() or "api"
        if mode not in ("api", "login"):
            print("Error: mode must be 'api' or 'login'.")
            sys.exit(1)
        profile_data["mode"] = mode

        if mode == "login":
            credentials_path = input("Credentials path (optional, auto-generate if empty): ").strip()
            if not credentials_path:
                credentials_path = f"~/.{ptype}-profiles/{name}"
            profile_data["credentials_path"] = credentials_path
        else:  # api mode
            base_url = input("Base URL: ").strip()
            if not base_url:
                print("Error: base URL cannot be empty.")
                sys.exit(1)
            if ptype == "claude":
                token = input("Auth token: ").strip()
                profile_data["base_url"] = base_url
                profile_data["token"] = token
            else:  # codex
                api_key = input("API key: ").strip()
                profile_data["base_url"] = base_url
                profile_data["api_key"] = api_key
    else:  # gemini - API mode only
        base_url = input("Base URL: ").strip()
        if not base_url:
            print("Error: base URL cannot be empty.")
            sys.exit(1)
        api_key = input("API key: ").strip()
        profile_data["base_url"] = base_url
        profile_data["api_key"] = api_key

    # Optional proxy for all types
    proxy = input("Proxy (optional, e.g., http://127.0.0.1:7890): ").strip()
    if proxy:
        profile_data["proxy"] = proxy

    config.setdefault("profiles", {})[name] = profile_data
    return config


def show_profile(config, name):
    profiles = config.get("profiles", {})
    if name not in profiles:
        print(f"Error: profile '{name}' not found.")
        sys.exit(1)

    profile_dict = profiles[name]
    profile = profile_from_dict(profile_dict)

    print(f"Profile: {name}")
    print(f"Type: {profile.type}")

    # Display mode for Claude and Codex types
    if profile.type in ("claude", "codex"):
        mode = profile_dict.get("mode", "api")
        print(f"Mode: {mode}")

        if mode == "login":
            credentials_path = profile_dict.get("credentials_path", "N/A")
            print(f"Credentials Path: {credentials_path}")
        else:  # api mode
            base_url = profile_dict.get("base_url", "N/A")
            if profile.type == "claude":
                token = profile_dict.get("token", "N/A")
                print(f"Base URL: {base_url}")
                print(f"Token: {token}")
            else:  # codex
                api_key = profile_dict.get("api_key", "N/A")
                print(f"Base URL: {base_url}")
                print(f"API Key: {api_key}")
    else:  # gemini
        base_url = profile_dict.get("base_url", "N/A")
        api_key = profile_dict.get("api_key", "N/A")
        print(f"Base URL: {base_url}")
        print(f"API Key: {api_key}")

    # Display proxy if set
    if profile.proxy:
        print(f"Proxy: {profile.proxy}")


def remove_profile(config, name):
    if name not in config.get("profiles", {}):
        print(f"Error: profile '{name}' not found.")
        sys.exit(1)
    del config["profiles"][name]
    print(f"Removed profile '{name}'.")
    return config
