import os
from pathlib import Path

# Loads a local .env file if present (no extra dependencies)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

# The API key is OPTIONAL: the app works without it, but with lower rate
# limits. With a free key (dev.pokemontcg.io) the limits are much higher.
API_KEY = os.environ.get("POKEMONTCG_API_KEY", "")
API_BASE_URL = "https://api.pokemontcg.io/v2"

# Path to the SQLite database (the local "cache" of cards)
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pokemon.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Host/port for hosting on the secondary server
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))

# Debug mode: MUST stay disabled in production. Werkzeug's debugger, if
# reachable over the network, allows arbitrary code execution on the
# server. Enable it only locally, explicitly, by setting FLASK_DEBUG=1
# in your .env or environment.
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

# Secret key used by Flask to sign session cookies. If SECRET_KEY is not
# set in the environment, a random one is generated once and stored in
# data/secret_key.txt so sessions survive server restarts. Never commit
# this file or share its contents.
_SECRET_KEY_PATH = Path(__file__).resolve().parent.parent / "data" / "secret_key.txt"


def _get_or_create_secret_key() -> str:
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if _SECRET_KEY_PATH.exists():
        return _SECRET_KEY_PATH.read_text().strip()
    import secrets
    key = secrets.token_hex(32)
    _SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SECRET_KEY_PATH.write_text(key)
    return key


# USD -> EUR exchange rate used to convert TCGplayer prices (USD)
# to match CardMarket prices (EUR) on collection/wishlist pages.
# Update it manually here or via the USD_TO_EUR_RATE environment variable.
USD_TO_EUR_RATE = float(os.environ.get("USD_TO_EUR_RATE", "0.92"))

SECRET_KEY = _get_or_create_secret_key()