import datetime
import re
import threading
import time
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

import db
import pokemon_api
from config import DEBUG, HOST, PORT, SECRET_KEY

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)

# Lock to prevent multiple concurrent requests from starting multiple
# preload threads in parallel (wasting external API calls and causing
# concurrent writes to the database).
_preload_lock = threading.Lock()
_preload_running = False

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")

# ---------- Simple in-memory rate limiting for login/register ----------
# Not shared across multiple server processes, but effective against a
# single attacker script hitting a single running instance (the realistic
# threat for a small self-hosted app like this one).
_attempt_lock = threading.Lock()
_failed_attempts: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 5 * 60
_RATE_LIMIT_MAX_ATTEMPTS = 5


def _rate_limit_key() -> str:
    # Prefer a real client IP if behind a proxy that sets it; fall back to
    # Flask's own remote_addr for direct connections.
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _is_rate_limited(key: str) -> bool:
    now = time.time()
    with _attempt_lock:
        attempts = [t for t in _failed_attempts.get(key, []) if now - t < _RATE_LIMIT_WINDOW_SECONDS]
        _failed_attempts[key] = attempts
        return len(attempts) >= _RATE_LIMIT_MAX_ATTEMPTS


def _record_failed_attempt(key: str):
    with _attempt_lock:
        _failed_attempts.setdefault(key, []).append(time.time())


def _clear_failed_attempts(key: str):
    with _attempt_lock:
        _failed_attempts.pop(key, None)


@app.before_request
def _ensure_db():
    db.init_db()


def login_required(view_func):
    """Rejects the request with 401 if there is no logged-in user in the
    session. All endpoints that read or write personal data use this."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return view_func(*args, **kwargs)
    return wrapped


# ---------- Authentication ----------

def _password_error(password: str) -> str | None:
    """Returns an error message if the password doesn't meet the minimum
    requirements, or None if it's acceptable. Kept deliberately light
    (length + one letter + one digit) so people aren't pushed toward
    writing it down somewhere insecure."""
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    return None


@app.route("/api/register", methods=["POST"])
def api_register():
    rl_key = _rate_limit_key()
    if _is_rate_limited(rl_key):
        return jsonify({"error": "Too many attempts. Please try again in a few minutes."}), 429

    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not EMAIL_RE.match(email):
        _record_failed_attempt(rl_key)
        return jsonify({"error": "Please enter a valid email address"}), 400

    if not USERNAME_RE.match(username):
        _record_failed_attempt(rl_key)
        return jsonify({"error": "Username must be 3-20 characters: letters, numbers, or underscore"}), 400

    password_error = _password_error(password)
    if password_error:
        _record_failed_attempt(rl_key)
        return jsonify({"error": password_error}), 400

    with db.get_conn() as conn:
        if db.get_user_by_email(conn, email):
            _record_failed_attempt(rl_key)
            return jsonify({"error": "An account with this email already exists"}), 409

        if db.get_user_by_username(conn, username):
            _record_failed_attempt(rl_key)
            return jsonify({"error": "This username is already taken"}), 409

        is_first_user = db.count_users(conn) == 0
        password_hash = generate_password_hash(password)
        user_id = db.create_user(conn, email, username, password_hash)

        if is_first_user:
            db.claim_legacy_data(conn, user_id)

    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    _clear_failed_attempts(rl_key)
    return jsonify({"id": user_id, "email": email, "username": username})


@app.route("/api/login", methods=["POST"])
def api_login():
    rl_key = _rate_limit_key()
    if _is_rate_limited(rl_key):
        return jsonify({"error": "Too many attempts. Please try again in a few minutes."}), 429

    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    with db.get_conn() as conn:
        user = db.get_user_by_email(conn, email)

    if not user or not check_password_hash(user["password_hash"], password):
        _record_failed_attempt(rl_key)
        return jsonify({"error": "Incorrect email or password"}), 401

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    _clear_failed_attempts(rl_key)
    return jsonify({"id": user["id"], "email": user["email"], "username": user["username"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me")
def api_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None})
    with db.get_conn() as conn:
        user = db.get_user_by_id(conn, user_id)
    if not user:
        session.clear()
        return jsonify({"user": None})
    return jsonify({"user": {"id": user["id"], "email": user["email"], "username": user["username"]}})


def _sync_set_core(conn, set_id: str):
    raw_cards = pokemon_api.fetch_cards_for_set(set_id)
    now = datetime.datetime.utcnow().isoformat()
    for raw in raw_cards:
        db.upsert_card(conn, pokemon_api.normalize_card(raw, set_id))
    db.mark_set_synced(conn, set_id, now)


def _preload_all_sets_worker():
    global _preload_running
    print("[Background Sync] Starting background card preload...")
    try:
        with db.get_conn() as conn:
            sets = db.get_all_sets(conn)

        for s in sets:
            set_id = s["id"]
            with db.get_conn() as conn:
                set_row = db.get_set(conn, set_id)
                if set_row and not set_row["last_synced"]:
                    print(f"[Background Sync] Downloading cards for: {s['name']} ({set_id})...")
                    try:
                        _sync_set_core(conn, set_id)
                        time.sleep(2)
                    except Exception as e:
                        print(f"[Background Sync] Error downloading {s['name']}: {e}")
                        time.sleep(5)
    except Exception as e:
        print(f"[Background Sync] Error in preload thread: {e}")
    finally:
        with _preload_lock:
            _preload_running = False
    print("[Background Sync] Preload completed successfully!")


def start_background_preload():
    global _preload_running
    with _preload_lock:
        if _preload_running:
            return
        _preload_running = True
    threading.Thread(target=_preload_all_sets_worker, daemon=True).start()


# ---------- Weekly automatic price refresh ----------
# Prices don't need to be re-downloaded on every visit, but they do go
# stale over time (cardmarket/tcgplayer prices shift week to week). This
# background job wakes up periodically and re-syncs any set whose prices
# are older than REFRESH_INTERVAL_DAYS, without any manual button.
REFRESH_INTERVAL_DAYS = 7
_REFRESH_CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # check every 6 hours

_weekly_refresh_lock = threading.Lock()
_weekly_refresh_started = False


def _weekly_refresh_worker():
    while True:
        try:
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=REFRESH_INTERVAL_DAYS)).isoformat()
            with db.get_conn() as conn:
                stale_sets = db.get_sets_needing_refresh(conn, cutoff)

            if stale_sets:
                print(f"[Weekly Refresh] {len(stale_sets)} set(s) have prices older than {REFRESH_INTERVAL_DAYS} days. Updating...")

            for s in stale_sets:
                set_id = s["id"]
                try:
                    with db.get_conn() as conn:
                        _sync_set_core(conn, set_id)
                    print(f"[Weekly Refresh] Updated prices for {s['name']} ({set_id}).")
                    time.sleep(2)
                except Exception as e:
                    print(f"[Weekly Refresh] Error updating {s['name']}: {e}")
                    time.sleep(5)
        except Exception as e:
            print(f"[Weekly Refresh] Error in refresh loop: {e}")

        time.sleep(_REFRESH_CHECK_INTERVAL_SECONDS)


def start_weekly_refresh():
    global _weekly_refresh_started
    with _weekly_refresh_lock:
        if _weekly_refresh_started:
            return
        _weekly_refresh_started = True
    threading.Thread(target=_weekly_refresh_worker, daemon=True).start()


@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/login.html")
def serve_login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.route("/set.html")
def serve_set_page():
    return send_from_directory(FRONTEND_DIR, "set.html")


@app.route("/collezione.html")
def serve_collection_page():
    return send_from_directory(FRONTEND_DIR, "collezione.html")


@app.route("/wishlist.html")
def serve_wishlist_page():
    return send_from_directory(FRONTEND_DIR, "wishlist.html")


@app.route("/binder.html")
def serve_binder_page():
    return send_from_directory(FRONTEND_DIR, "binder.html")


@app.route("/api/sets")
@login_required
def api_list_sets():
    user_id = session["user_id"]
    with db.get_conn() as conn:
        rows = db.get_all_sets(conn, user_id)
        if rows:
            start_background_preload()
            return jsonify([dict(r) for r in rows])

    try:
        raw_sets = pokemon_api.fetch_sets()
    except pokemon_api.PokemonAPIError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error contacting the API: {e}"}), 502

    with db.get_conn() as conn:
        for raw in raw_sets:
            db.upsert_set(conn, pokemon_api.normalize_set(raw))
        rows = db.get_all_sets(conn, user_id)
        start_background_preload()
        return jsonify([dict(r) for r in rows])


@app.route("/api/sets/refresh", methods=["POST"])
@login_required
def api_refresh_sets():
    try:
        raw_sets = pokemon_api.fetch_sets()
    except pokemon_api.PokemonAPIError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error contacting the API: {e}"}), 502

    with db.get_conn() as conn:
        for raw in raw_sets:
            db.upsert_set(conn, pokemon_api.normalize_set(raw))
        rows = db.get_all_sets(conn, session["user_id"])
        start_background_preload()
        return jsonify([dict(r) for r in rows])


@app.route("/api/sets/<set_id>/cards")
@login_required
def api_get_set_cards(set_id):
    user_id = session["user_id"]
    rarity = request.args.get("rarity")
    with db.get_conn() as conn:
        set_row = db.get_set(conn, set_id)
        cards = db.get_cards_for_set(conn, set_id, rarity, user_id)

        if not cards and (not set_row or not set_row["last_synced"]):
            synced = _sync_set(conn, set_id)
            if isinstance(synced, tuple):
                return synced
            cards = db.get_cards_for_set(conn, set_id, rarity, user_id)
            set_row = db.get_set(conn, set_id)

        rarities = db.get_rarities_for_set(conn, set_id)
        return jsonify({
            "set": dict(set_row) if set_row else None,
            "cards": [dict(c) for c in cards],
            "available_rarities": rarities,
        })


@app.route("/api/sets/<set_id>/refresh", methods=["POST"])
@login_required
def api_refresh_set_cards(set_id):
    user_id = session["user_id"]
    with db.get_conn() as conn:
        result = _sync_set(conn, set_id)
        if isinstance(result, tuple):
            return result
        cards = db.get_cards_for_set(conn, set_id, None, user_id)
        rarities = db.get_rarities_for_set(conn, set_id)
        set_row = db.get_set(conn, set_id)
        return jsonify({
            "set": dict(set_row) if set_row else None,
            "cards": [dict(c) for c in cards],
            "available_rarities": rarities,
        })


def _sync_set(conn, set_id: str):
    try:
        _sync_set_core(conn, set_id)
    except pokemon_api.PokemonAPIError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error contacting the API: {e}"}), 502
    return None


# ---------- API: Advanced search with sanitization for binder internals ----------

@app.route("/api/cards/search")
@login_required
def api_search_cards():
    user_id = session["user_id"]
    name = request.args.get("name", "").strip()
    rarity = request.args.get("rarity")
    pokedex_number = request.args.get("pokedex_number")

    # Numeric conversion for SQLite
    if pokedex_number and pokedex_number.strip():
        try:
            pokedex_number = int(pokedex_number)
        except ValueError:
            pokedex_number = None
    else:
        pokedex_number = None

    with db.get_conn() as conn:
        cards = db.search_cards_global(conn, name if name else None, rarity, pokedex_number, user_id)

    # If the local database is empty, query the official API live
    if not cards:
        if pokedex_number:
            print(f"[Search] Local database empty for Dex #{pokedex_number}. Downloading live data...")
            try:
                raw_cards = pokemon_api.fetch_cards_by_pokedex(pokedex_number)
                if raw_cards:
                    with db.get_conn() as conn:
                        for raw in raw_cards:
                            s_id = raw.get("set", {}).get("id")
                            if s_id and not db.get_set(conn, s_id):
                                db.upsert_set(conn, pokemon_api.normalize_set(raw.get("set", {})))
                            db.upsert_card(conn, pokemon_api.normalize_card(raw, s_id))
                        cards = db.search_cards_global(conn, name if name else None, rarity, pokedex_number, user_id)
            except Exception as e:
                print(f"Dex fallback error: {e}")

        elif name and len(name) >= 2:
            print(f"[Search] Local database empty for '{name}'. Downloading live data...")
            try:
                raw_cards = pokemon_api.fetch_cards_by_name(name)
                if raw_cards:
                    with db.get_conn() as conn:
                        for raw in raw_cards:
                            s_id = raw.get("set", {}).get("id")
                            if s_id and not db.get_set(conn, s_id):
                                db.upsert_set(conn, pokemon_api.normalize_set(raw.get("set", {})))
                            db.upsert_card(conn, pokemon_api.normalize_card(raw, s_id))
                        cards = db.search_cards_global(conn, name, rarity, pokedex_number, user_id)
            except Exception as e:
                print(f"Name fallback error: {e}")

    return jsonify([dict(c) for c in cards])


@app.route("/api/rarities")
@login_required
def api_global_rarities():
    name = request.args.get("name")
    with db.get_conn() as conn:
        rarities = db.get_all_global_rarities(conn, name)
        return jsonify(rarities)


@app.route("/api/collection")
@login_required
def api_get_collection():
    with db.get_conn() as conn:
        rows = db.get_user_collection(conn, session["user_id"])
        return jsonify([dict(r) for r in rows])


@app.route("/api/collection/toggle", methods=["POST"])
@login_required
def api_toggle_collection():
    data = request.json or {}
    card_id = data.get("card_id")
    if not card_id:
        return jsonify({"error": "Missing ID"}), 400
    with db.get_conn() as conn:
        is_owned = db.toggle_card_ownership(conn, session["user_id"], card_id)
        return jsonify({"is_owned": is_owned})


@app.route("/api/wishlist")
@login_required
def api_get_wishlist():
    with db.get_conn() as conn:
        rows = db.get_user_wishlist(conn, session["user_id"])
        return jsonify([dict(r) for r in rows])


@app.route("/api/wishlist/toggle", methods=["POST"])
@login_required
def api_toggle_wishlist():
    data = request.json or {}
    card_id = data.get("card_id")
    if not card_id:
        return jsonify({"error": "Missing ID"}), 400
    with db.get_conn() as conn:
        is_wished = db.toggle_wishlist_ownership(conn, session["user_id"], card_id)
        return jsonify({"is_wished": is_wished})


@app.route("/api/sets/toggle-favorite", methods=["POST"])
@login_required
def api_toggle_set_favorite():
    data = request.json or {}
    set_id = data.get("set_id")
    if not set_id:
        return jsonify({"error": "Missing ID"}), 400
    with db.get_conn() as conn:
        is_favorite = db.toggle_set_favorite(conn, session["user_id"], set_id)
        return jsonify({"is_favorite": is_favorite})


@app.route("/api/binders", methods=["GET", "POST"])
@login_required
def api_manage_binders():
    user_id = session["user_id"]
    if request.method == "POST":
        data = request.json or {}
        name = (data.get("name") or "New Binder").strip()[:100]
        color = data.get("color", "#242230")
        b_type = data.get("type", "custom")
        if b_type not in ("custom", "pokedex"):
            b_type = "custom"

        try:
            rows = int(data.get("rows", 3))
            cols = int(data.get("cols", 3))
        except (TypeError, ValueError):
            return jsonify({"error": "Rows and columns must be integers"}), 400

        if not (1 <= rows <= 5) or not (1 <= cols <= 5):
            return jsonify({"error": "Rows and columns must be between 1 and 5"}), 400

        if b_type == "pokedex":
            rows, cols = 3, 3

        with db.get_conn() as conn:
            new_id = db.create_binder(conn, user_id, name, color, rows, cols, b_type)
            return jsonify({"id": new_id, "success": True})
    with db.get_conn() as conn:
        rows = db.get_all_binders(conn, user_id)
        return jsonify([dict(r) for r in rows])


@app.route("/api/binders/<int:binder_id>", methods=["GET", "DELETE"])
@login_required
def api_single_binder(binder_id):
    user_id = session["user_id"]
    with db.get_conn() as conn:
        if request.method == "DELETE":
            db.delete_binder(conn, binder_id, user_id)
            return jsonify({"success": True})
        b = db.get_binder(conn, binder_id, user_id)
        if not b:
            return jsonify({"error": "Binder not found"}), 404
        slots = db.get_binder_slots(conn, binder_id)
        return jsonify({"binder": dict(b), "slots": {s["slot_number"]: dict(s) for s in slots}})


@app.route("/api/binders/<int:binder_id>/slots", methods=["POST"])
@login_required
def api_assign_slot(binder_id):
    user_id = session["user_id"]
    data = request.json or {}
    try:
        slot_number = int(data.get("slot_number"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid slot number"}), 400

    if slot_number < 1:
        return jsonify({"error": "Invalid slot number"}), 400

    card_id = data.get("card_id")
    with db.get_conn() as conn:
        binder = db.get_binder(conn, binder_id, user_id)
        if not binder:
            return jsonify({"error": "Binder not found"}), 404
        max_slot = 1025 if binder["type"] == "pokedex" else binder["rows"] * binder["cols"] * 200
        if slot_number > max_slot:
            return jsonify({"error": "Slot number is outside the binder's limits"}), 400
        db.set_binder_slot(conn, binder_id, slot_number, card_id if card_id else None)
        return jsonify({"success": True})


if __name__ == "__main__":
    db.init_db()
    start_weekly_refresh()
    app.run(host=HOST, port=PORT, debug=DEBUG)