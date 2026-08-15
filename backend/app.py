import datetime
import re
import threading
import time
from functools import wraps
from pathlib import Path
import uuid

# Richiede: pip install Pillow
from PIL import Image, UnidentifiedImageError

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

import db
import pokemon_api
# Importata MAX_CONTENT_LENGTH dalla config
from config import DEBUG, HOST, PORT, SECRET_KEY, USD_TO_EUR_RATE, MAX_CONTENT_LENGTH

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = not DEBUG  # Cookie sicuri solo in produzione
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=30)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH  # Limite dimensione body (5MB)

# Inizializza il DB all'avvio, non ad ogni richiesta
db.init_db()

_preload_lock = threading.Lock()
_preload_running = False

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

_attempt_lock = threading.Lock()
_failed_attempts: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW_SECONDS = 5 * 60
_RATE_LIMIT_MAX_ATTEMPTS = 5

@app.after_request
def add_security_headers(response):
    """Inietta header di sicurezza per prevenire XSS, Clickjacking e sniffing."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    if not DEBUG:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Content Security Policy adattata per i domini esterni usati e blob per l'upload
    csp = (
        "default-src 'self'; "
        "img-src 'self' data: blob: https: http:; " 
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline';"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

def _rate_limit_key() -> str:
    # Ignora X-Forwarded-For per prevenire lo spoofing
    # Nota: se usi un reverse proxy (Nginx), abilita Werkzeug ProxyFix.
    return request.remote_addr or "unknown"

def _is_rate_limited(key: str, max_attempts: int = _RATE_LIMIT_MAX_ATTEMPTS, window: int = _RATE_LIMIT_WINDOW_SECONDS) -> bool:
    now = time.time()
    with _attempt_lock:
        attempts = [t for t in _failed_attempts.get(key, []) if now - t < window]
        _failed_attempts[key] = attempts
        return len(attempts) >= max_attempts

def _record_attempt(key: str):
    with _attempt_lock:
        _failed_attempts.setdefault(key, []).append(time.time())

def _clear_failed_attempts(key: str):
    with _attempt_lock:
        _failed_attempts.pop(key, None)

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return view_func(*args, **kwargs)
    return wrapped

@app.route("/api/exchange-rate")
@login_required
def api_exchange_rate():
    return jsonify({"usd_to_eur": USD_TO_EUR_RATE})

def _is_admin(user_id) -> bool:
    # Verifica il flag sul database invece di un ID fisso. 
    with db.get_conn() as conn:
        user = db.get_user_by_id(conn, user_id)
        return bool(user and user["is_admin"])

def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        if not _is_admin(session["user_id"]):
            return jsonify({"error": "Admin access required"}), 403
        return view_func(*args, **kwargs)
    return wrapped

@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file sent"}), 400
        
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
        
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Extension not allowed"}), 400

    try:
        # Verifica tramite Pillow che il contenuto sia effettivamente un'immagine valida
        img = Image.open(file.stream)
        img.verify()
        file.stream.seek(0) # Resetta il puntatore dopo il verify
    except (UnidentifiedImageError, Exception):
        return jsonify({"error": "Invalid image file format"}), 400

    uploads_dir = FRONTEND_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    file.save(str(uploads_dir / filename))
    return jsonify({"url": f"uploads/{filename}"})

# ---------- Authentication ----------

def _password_error(password: str) -> str | None:
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
    remember = data.get("remember", False)

    if not EMAIL_RE.match(email):
        _record_attempt(rl_key)
        return jsonify({"error": "Please enter a valid email address"}), 400

    if not USERNAME_RE.match(username):
        _record_attempt(rl_key)
        return jsonify({"error": "Username must be 3-20 characters: letters, numbers, or underscore"}), 400

    password_error = _password_error(password)
    if password_error:
        _record_attempt(rl_key)
        return jsonify({"error": password_error}), 400

    with db.get_conn() as conn:
        if db.get_user_by_email(conn, email):
            _record_attempt(rl_key)
            return jsonify({"error": "An account with this email already exists"}), 409

        if db.get_user_by_username(conn, username):
            _record_attempt(rl_key)
            return jsonify({"error": "This username is already taken"}), 409

        is_first_user = db.count_users(conn) == 0
        password_hash = generate_password_hash(password)
        # Il primo utente viene automaticamente promosso admin
        is_admin_flag = 1 if is_first_user else 0
        user_id = db.create_user(conn, email, username, password_hash, is_admin_flag)

        if is_first_user:
            db.claim_legacy_data(conn, user_id)

    session.clear()
    session["user_id"] = user_id
    session.permanent = bool(remember)
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
    remember = data.get("remember", False)

    with db.get_conn() as conn:
        user = db.get_user_by_email(conn, email)

    if not user or not check_password_hash(user["password_hash"], password):
        _record_attempt(rl_key)
        return jsonify({"error": "Incorrect email or password"}), 401

    session.clear()
    session["user_id"] = user["id"]
    session.permanent = bool(remember)
    _clear_failed_attempts(rl_key)
    return jsonify({"id": user["id"], "email": user["email"], "username": user["username"]})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})

ALLOWED_AVATAR_IDS = set(range(1, 152)) | {196, 197, 470, 471, 700, 778}

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
    return jsonify({"user": {
        "id": user["id"],
        "email": user["email"],
        "username": user["username"],
        "is_admin": _is_admin(user["id"]),
        "avatar_pokemon_id": user["avatar_pokemon_id"],
    }})

@app.route("/api/me/avatar", methods=["POST"])
@login_required
def api_set_avatar():
    data = request.json or {}
    try:
        pokemon_id = int(data.get("pokemon_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid Pokémon ID"}), 400
    if pokemon_id not in ALLOWED_AVATAR_IDS:
        return jsonify({"error": "This Pokémon isn't available as an avatar"}), 400
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET avatar_pokemon_id = ? WHERE id = ?", (pokemon_id, session["user_id"]))
    return jsonify({"success": True, "avatar_pokemon_id": pokemon_id})

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

_force_resync_lock = threading.Lock()
_force_resync_running = False
_force_resync_status = {"running": False, "total": 0, "done": 0, "current_set": None}

def _force_resync_all_worker():
    global _force_resync_running
    print("[Admin Resync] Avvio resync FORZATO di tutti i set...")
    try:
        with db.get_conn() as conn:
            sets = db.get_all_sets(conn)
        _force_resync_status["total"] = len(sets)
        _force_resync_status["done"] = 0

        for s in sets:
            set_id = s["id"]
            _force_resync_status["current_set"] = s["name"]
            try:
                with db.get_conn() as conn:
                    _sync_set_core(conn, set_id)
                print(f"[Admin Resync] Sincronizzato {s['name']} ({set_id})")
                time.sleep(2)
            except Exception as e:
                print(f"[Admin Resync] Errore su {s['name']}: {e}")
                time.sleep(5)
            _force_resync_status["done"] += 1
    except Exception as e:
        print(f"[Admin Resync] Errore generale: {e}")
    finally:
        with _force_resync_lock:
            _force_resync_running = False
        _force_resync_status["running"] = False
        _force_resync_status["current_set"] = None
    print("[Admin Resync] Completato!")

def start_force_resync_all() -> bool:
    global _force_resync_running
    with _force_resync_lock:
        if _force_resync_running:
            return False
        _force_resync_running = True
    _force_resync_status["running"] = True
    threading.Thread(target=_force_resync_all_worker, daemon=True).start()
    return True

@app.route("/api/admin/resync-all", methods=["POST"])
@admin_required
def api_admin_resync_all():
    if not start_force_resync_all():
        return jsonify({"error": "A resync is already in progress"}), 409
    return jsonify({"success": True})

@app.route("/api/admin/resync-status")
@admin_required
def api_admin_resync_status():
    return jsonify(_force_resync_status)

REFRESH_INTERVAL_DAYS = 7
_REFRESH_CHECK_INTERVAL_SECONDS = 6 * 60 * 60

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
        valid_ids = []
        for raw in raw_sets:
            valid_ids.append(raw["id"])
            db.upsert_set(conn, pokemon_api.normalize_set(raw))
            
        if valid_ids:
            db.purge_unlisted_sets(conn, valid_ids)

        rows = db.get_all_sets(conn, user_id)
        start_background_preload()
        return jsonify([dict(r) for r in rows])

@app.route("/api/sets/refresh", methods=["POST"])
@login_required
def api_refresh_sets():
    rl_key = f"sync_api_{_rate_limit_key()}"
    if _is_rate_limited(rl_key, max_attempts=3, window=60):
        return jsonify({"error": "Too many refresh attempts. Please wait."}), 429

    try:
        raw_sets = pokemon_api.fetch_sets()
        _record_attempt(rl_key)
    except pokemon_api.PokemonAPIError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error contacting the API: {e}"}), 502

    with db.get_conn() as conn:
        valid_ids = []
        for raw in raw_sets:
            valid_ids.append(raw["id"])
            db.upsert_set(conn, pokemon_api.normalize_set(raw))
            
        if valid_ids:
            db.purge_unlisted_sets(conn, valid_ids)

        rows = db.get_all_sets(conn, session["user_id"])
        start_background_preload()
        return jsonify([dict(r) for r in rows])

@app.route("/api/sets/<set_id>/cards")
@login_required
def api_get_set_cards(set_id):
    user_id = session["user_id"]
    rarity = request.args.get("rarity")
    card_type = request.args.get("type")
    with db.get_conn() as conn:
        set_row = db.get_set(conn, set_id)
        cards = db.get_cards_for_set(conn, set_id, rarity, user_id, card_type)

        if not cards and (not set_row or not set_row["last_synced"]):
            synced = _sync_set(conn, set_id)
            if isinstance(synced, tuple):
                return synced
            cards = db.get_cards_for_set(conn, set_id, rarity, user_id, card_type)
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
    rl_key = f"sync_set_{set_id}_{_rate_limit_key()}"
    if _is_rate_limited(rl_key, max_attempts=2, window=60):
        return jsonify({"error": "Too many refresh attempts for this set. Please wait."}), 429

    user_id = session["user_id"]
    with db.get_conn() as conn:
        result = _sync_set(conn, set_id)
        _record_attempt(rl_key)
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

@app.route("/api/cards/search")
@login_required
def api_search_cards():
    user_id = session["user_id"]
    name = request.args.get("name", "").strip()
    rarity = request.args.get("rarity")
    pokedex_number = request.args.get("pokedex_number")
    card_type = request.args.get("type")
    set_id = request.args.get("set_id")

    if pokedex_number and pokedex_number.strip():
        try:
            pokedex_number = int(pokedex_number)
        except ValueError:
            pokedex_number = None
    else:
        pokedex_number = None

    with db.get_conn() as conn:
        cards = db.search_cards_global(conn, name if name else None, rarity, pokedex_number, user_id, card_type, set_id)

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
                        cards = db.search_cards_global(conn, name if name else None, rarity, pokedex_number, user_id, card_type, set_id)
            except Exception as e:
                print(f"Dex fallback error: {e}")

        elif name and len(name) >= 1:
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
                        cards = db.search_cards_global(conn, name, rarity, pokedex_number, user_id, card_type, set_id)
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

@app.route("/api/types")
@login_required
def api_global_types():
    with db.get_conn() as conn:
        types = db.get_all_global_types(conn)
        return jsonify(types)

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

@app.route("/api/wishlist/uncategorized")
@login_required
def api_wishlist_uncategorized():
    with db.get_conn() as conn:
        rows = db.get_uncategorized_wishlist(conn, session["user_id"])
        return jsonify([dict(r) for r in rows])

@app.route("/api/wishlist/boards", methods=["GET", "POST"])
@login_required
def api_wishlist_boards():
    user_id = session["user_id"]
    if request.method == "POST":
        data = request.json or {}
        name = (data.get("name") or "").strip()[:60]
        color = data.get("color") or "#a855f7"
        if not name:
            return jsonify({"error": "Board name cannot be empty"}), 400
        if not _HEX_COLOR_RE.match(color):
            color = "#a855f7"
        with db.get_conn() as conn:
            new_id = db.create_wishlist_board(conn, user_id, name, color)
            return jsonify({"id": new_id, "success": True})
    with db.get_conn() as conn:
        rows = db.get_wishlist_boards(conn, user_id)
        return jsonify([dict(r) for r in rows])

@app.route("/api/wishlist/boards/reorder", methods=["POST"])
@login_required
def api_reorder_wishlist_boards():
    data = request.json or {}
    board_ids = data.get("board_ids")
    if not isinstance(board_ids, list):
        return jsonify({"error": "board_ids must be a list"}), 400
    with db.get_conn() as conn:
        db.reorder_wishlist_boards(conn, session["user_id"], board_ids)
    return jsonify({"success": True})

@app.route("/api/wishlist/boards/<int:board_id>/cards/reorder", methods=["POST"])
@login_required
def api_reorder_board_cards(board_id):
    user_id = session["user_id"]
    data = request.json or {}
    card_ids = data.get("card_ids")
    if not isinstance(card_ids, list):
        return jsonify({"error": "card_ids must be a list"}), 400
    with db.get_conn() as conn:
        board = db.get_wishlist_board(conn, board_id, user_id)
        if not board:
            return jsonify({"error": "Board not found"}), 404
        db.reorder_board_cards(conn, board_id, card_ids)
    return jsonify({"success": True})

@app.route("/api/wishlist/boards/<int:board_id>", methods=["GET", "PATCH", "DELETE"])
@login_required
def api_wishlist_board_single(board_id):
    user_id = session["user_id"]
    with db.get_conn() as conn:
        board = db.get_wishlist_board(conn, board_id, user_id)
        if not board:
            return jsonify({"error": "Board not found"}), 404

        if request.method == "DELETE":
            db.delete_wishlist_board(conn, board_id, user_id)
            return jsonify({"success": True})

        if request.method == "PATCH":
            data = request.json or {}
            name = data.get("name")
            color = data.get("color")
            if name is not None:
                name = name.strip()[:60]
                if not name:
                    return jsonify({"error": "Name cannot be empty"}), 400
            if color is not None and not _HEX_COLOR_RE.match(color):
                return jsonify({"error": "Invalid color"}), 400
            db.update_wishlist_board(conn, board_id, user_id, name=name, color=color)
            updated = db.get_wishlist_board(conn, board_id, user_id)
            return jsonify(dict(updated))

        cards = db.get_wishlist_board_cards(conn, board_id)
        return jsonify({"board": dict(board), "cards": [dict(c) for c in cards]})

@app.route("/api/wishlist/boards/<int:board_id>/cards", methods=["POST"])
@login_required
def api_wishlist_board_add_card(board_id):
    user_id = session["user_id"]
    data = request.json or {}
    card_id = data.get("card_id")
    if not card_id:
        return jsonify({"error": "Missing card ID"}), 400
    with db.get_conn() as conn:
        board = db.get_wishlist_board(conn, board_id, user_id)
        if not board:
            return jsonify({"error": "Board not found"}), 404
        in_wishlist = conn.execute(
            "SELECT 1 FROM wishlist WHERE user_id = ? AND card_id = ?", (user_id, card_id)
        ).fetchone()
        if not in_wishlist:
            return jsonify({"error": "This card is not in your wishlist"}), 400
        db.add_card_to_board(conn, board_id, card_id)
        return jsonify({"success": True})

@app.route("/api/wishlist/boards/<int:board_id>/cards/<card_id>", methods=["DELETE"])
@login_required
def api_wishlist_board_remove_card(board_id, card_id):
    user_id = session["user_id"]
    with db.get_conn() as conn:
        board = db.get_wishlist_board(conn, board_id, user_id)
        if not board:
            return jsonify({"error": "Board not found"}), 404
        db.remove_card_from_board(conn, board_id, card_id)
        return jsonify({"success": True})

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

@app.route("/api/sets/favorites/reorder", methods=["POST"])
@login_required
def api_reorder_favorite_sets():
    data = request.json or {}
    set_ids = data.get("set_ids")
    if not isinstance(set_ids, list) or not all(isinstance(s, str) for s in set_ids):
        return jsonify({"error": "set_ids must be a list of set IDs"}), 400
    with db.get_conn() as conn:
        db.reorder_favorite_sets(conn, session["user_id"], set_ids)
    return jsonify({"success": True})

@app.route("/api/binders", methods=["GET", "POST"])
@login_required
def api_manage_binders():
    user_id = session["user_id"]
    if request.method == "POST":
        data = request.json or {}
        name = (data.get("name") or "New Binder").strip()[:100]
        color = data.get("color", "#242230")
        inner_color = data.get("inner_color") or color
        panel_color = data.get("panel_color") or "#16141d"
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
            new_id = db.create_binder(conn, user_id, name, color, rows, cols, b_type, inner_color, panel_color)
            return jsonify({"id": new_id, "success": True})
    with db.get_conn() as conn:
        rows = db.get_all_binders(conn, user_id)
        return jsonify([dict(r) for r in rows])

@app.route("/api/binders/<int:binder_id>", methods=["GET", "POST", "PATCH", "DELETE"])
@login_required
def api_single_binder(binder_id):
    user_id = session["user_id"]
    if request.method == "POST":
        return jsonify({"error": "Metodo non consentito. Utilizzare PATCH per le impostazioni e POST su /slots per posizionare le carte."}), 400

    with db.get_conn() as conn:
        if request.method == "DELETE":
            b = db.get_binder(conn, binder_id, user_id)
            if not b:
                return jsonify({"error": "Binder not found"}), 404
            
            # Trova le immagini custom da eliminare prima di droppare il binder
            slots = db.get_binder_slots(conn, binder_id)
            custom_images = [s["custom_image_url"] for s in slots if s["custom_image_url"]]
            
            db.delete_binder(conn, binder_id, user_id)
            
            # Elimina fisicamente i file
            for img_url in custom_images:
                try:
                    filename = img_url.split("/")[-1]
                    filepath = FRONTEND_DIR / "uploads" / filename
                    if filepath.exists():
                        filepath.unlink()
                except:
                    pass
            
            return jsonify({"success": True})

        if request.method == "PATCH":
            data = request.json or {}
            name = data.get("name")
            color = data.get("color")
            inner_color = data.get("inner_color")
            panel_color = data.get("panel_color")

            if name is not None:
                name = name.strip()[:100]
                if not name:
                    return jsonify({"error": "Name cannot be empty"}), 400
            if color is not None and not _HEX_COLOR_RE.match(color):
                return jsonify({"error": "Invalid cover color"}), 400
            if inner_color is not None and not _HEX_COLOR_RE.match(inner_color):
                return jsonify({"error": "Invalid inner color"}), 400
            if panel_color is not None and not _HEX_COLOR_RE.match(panel_color):
                return jsonify({"error": "Invalid panel color"}), 400

            updated = db.update_binder(conn, binder_id, user_id, name=name, color=color, inner_color=inner_color, panel_color=panel_color)
            if not updated:
                return jsonify({"error": "Binder not found"}), 404
            b = db.get_binder(conn, binder_id, user_id)
            return jsonify(dict(b))

        b = db.get_binder(conn, binder_id, user_id)
        if not b:
            return jsonify({"error": "Binder not found"}), 404
        slots = db.get_binder_slots(conn, binder_id)
        return jsonify({"binder": dict(b), "slots": {s["slot_number"]: dict(s) for s in slots}})

@app.route("/api/binders/<int:binder_id>/slots", methods=["GET", "POST"])
@login_required
def api_assign_slot(binder_id):
    user_id = session["user_id"]
    if request.method == "GET":
        with db.get_conn() as conn:
            slots = db.get_binder_slots(conn, binder_id)
            return jsonify({"slots": {s["slot_number"]: dict(s) for s in slots}})

    data = request.json or {}
    try:
        slot_number = int(data.get("slot_number"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid slot number"}), 400

    if slot_number < 1:
        return jsonify({"error": "Invalid slot number"}), 400

    card_id = data.get("card_id")
    custom_image_url = data.get("custom_image_url")
    try:
        slot_span = int(data.get("slot_span", 1))
    except (TypeError, ValueError):
        slot_span = 1

    with db.get_conn() as conn:
        binder = db.get_binder(conn, binder_id, user_id)
        if not binder:
            return jsonify({"error": "Binder not found"}), 404
        max_slot = 1025 if binder["type"] == "pokedex" else binder["rows"] * binder["cols"] * 200
        if slot_number > max_slot:
            return jsonify({"error": "Slot number is outside the binder's limits"}), 400
            
        # Identifica se c'era una vecchia immagine custom da eliminare
        slots = db.get_binder_slots(conn, binder_id)
        old_image_url = None
        for s in slots:
            if s["slot_number"] == slot_number:
                old_image_url = s["custom_image_url"]
                break

        db.set_binder_slot(conn, binder_id, slot_number, card_id if card_id else None, custom_image_url, slot_span)
        
        # Se l'immagine è cambiata o lo slot è stato svuotato, elimina il vecchio file
        if old_image_url and old_image_url != custom_image_url:
            try:
                filename = old_image_url.split("/")[-1]
                filepath = FRONTEND_DIR / "uploads" / filename
                if filepath.exists():
                    filepath.unlink()
            except:
                pass
                
        return jsonify({"success": True})

if __name__ == "__main__":
    start_weekly_refresh()
    app.run(host=HOST, port=PORT, debug=DEBUG)