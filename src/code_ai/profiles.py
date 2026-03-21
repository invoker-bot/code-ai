import sys


VALID_TYPES = ("claude", "gemini", "codex")


def list_profiles(config):
    profiles = config.get("profiles", {})
    if not profiles:
        print("No profiles configured.")
        return
    print(f"{'Name':<20} {'Type':<10} {'Base URL'}")
    print("-" * 60)
    for name, p in profiles.items():
        print(f"{name:<20} {p['type']:<10} {p.get('base_url', '')}")


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

    # Handle mode for Claude
    if ptype == "claude":
        mode = input("Mode (api/login) [api]: ").strip().lower() or "api"
        if mode not in ("api", "login"):
            print("Error: mode must be 'api' or 'login'.")
            sys.exit(1)
        profile_data["mode"] = mode

        if mode == "login":
            credentials_path = input("Credentials path: ").strip()
            if not credentials_path:
                print("Error: credentials path cannot be empty.")
                sys.exit(1)
            profile_data["credentials_path"] = credentials_path
        else:  # api mode
            base_url = input("Base URL: ").strip()
            if not base_url:
                print("Error: base URL cannot be empty.")
                sys.exit(1)
            token = input("Auth token: ").strip()
            profile_data["base_url"] = base_url
            profile_data["token"] = token
    else:  # gemini or codex - API mode only
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
    from .models import profile_from_dict

    profiles = config.get("profiles", {})
    if name not in profiles:
        print(f"Error: profile '{name}' not found.")
        sys.exit(1)

    profile_dict = profiles[name]
    profile = profile_from_dict(profile_dict)

    print(f"Profile: {name}")
    print(f"Type: {profile.type}")

    # Display mode for Claude type
    if profile.type == "claude":
        mode = profile_dict.get("mode", "api")
        print(f"Mode: {mode}")

        if mode == "login":
            credentials_path = profile_dict.get("credentials_path", "N/A")
            print(f"Credentials Path: {credentials_path}")
        else:  # api mode
            base_url = profile_dict.get("base_url", "N/A")
            token = profile_dict.get("token", "N/A")
            print(f"Base URL: {base_url}")
            print(f"Token: {token}")
    else:  # gemini or codex
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
