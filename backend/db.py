import sqlite3
from contextlib import contextmanager

from config import DB_PATH

# MULTI-USER SCHEMA NOTE:
# - "sets" and "cards" remain global tables (shared product catalog).
# - "collection", "wishlist" and "favorite_sets" now have a composite
#   primary key (user_id, ...) so each user can own/want the same card
#   independently of other users.
# - "binders" has a user_id column to know who owns each binder.
SCHEMA = """
CREATE TABLE IF NOT EXISTS sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    release_date TEXT,
    logo_url TEXT,
    symbol_url TEXT,
    total_cards INTEGER,
    last_synced TEXT
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL,
    name TEXT NOT NULL,
    card_number TEXT,
    rarity TEXT,
    image_small TEXT,
    image_large TEXT,
    price_market REAL,
    price_low REAL,
    price_mid REAL,
    price_high REAL,
    currency TEXT,
    last_updated TEXT,
    national_dex INTEGER,
    types TEXT,
    FOREIGN KEY (set_id) REFERENCES sets (id)
);

CREATE INDEX IF NOT EXISTS idx_cards_set_id ON cards (set_id);
CREATE INDEX IF NOT EXISTS idx_cards_rarity ON cards (rarity);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    username TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection (
    user_id INTEGER NOT NULL,
    card_id TEXT NOT NULL,
    PRIMARY KEY (user_id, card_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (card_id) REFERENCES cards (id)
);

CREATE TABLE IF NOT EXISTS favorite_sets (
    user_id INTEGER NOT NULL,
    set_id TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, set_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (set_id) REFERENCES sets (id)
);

CREATE TABLE IF NOT EXISTS wishlist (
    user_id INTEGER NOT NULL,
    card_id TEXT NOT NULL,
    PRIMARY KEY (user_id, card_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (card_id) REFERENCES cards (id)
);

CREATE TABLE IF NOT EXISTS binders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    inner_color TEXT,
    panel_color TEXT,
    rows INTEGER DEFAULT 3,
    cols INTEGER DEFAULT 3,
    type TEXT DEFAULT 'custom',
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS binder_slots (
    binder_id INTEGER,
    slot_number INTEGER,
    card_id TEXT,
    custom_image_url TEXT,
    slot_span INTEGER DEFAULT 1,
    PRIMARY KEY (binder_id, slot_number),
    FOREIGN KEY (binder_id) REFERENCES binders (id),
    FOREIGN KEY (card_id) REFERENCES cards (id)
);

CREATE TABLE IF NOT EXISTS wishlist_boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#a855f7',
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS wishlist_board_cards (
    board_id INTEGER NOT NULL,
    card_id TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    PRIMARY KEY (board_id, card_id),
    FOREIGN KEY (board_id) REFERENCES wishlist_boards (id),
    FOREIGN KEY (card_id) REFERENCES cards (id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _column_exists(conn, table: str, column: str) -> bool:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _migrate_to_multiuser(conn):
    """Upgrades a database created BEFORE the multi-user system to the new."""
    for table, id_col in (("collection", "card_id"), ("wishlist", "card_id"), ("favorite_sets", "set_id")):
        if _table_exists(conn, table) and not _column_exists(conn, table, "user_id"):
            legacy_name = f"{table}_legacy"
            if not _table_exists(conn, legacy_name):
                conn.execute(f"ALTER TABLE {table} RENAME TO {legacy_name}")
                print(f"[Database] Pre-existing data from '{table}' preserved in '{legacy_name}', waiting for an account.")
            else:
                conn.execute(f"DROP TABLE {table}")
            conn.execute(f"""
                CREATE TABLE {table} (
                    user_id INTEGER NOT NULL,
                    {id_col} TEXT NOT NULL,
                    {"sort_order INTEGER DEFAULT 0," if table == "favorite_sets" else ""}
                    PRIMARY KEY (user_id, {id_col}),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

    if _table_exists(conn, "binders") and not _column_exists(conn, "binders", "user_id"):
        conn.execute("ALTER TABLE binders ADD COLUMN user_id INTEGER")
        print("[Database] 'user_id' column added to binders (existing binders waiting for an account).")


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        try:
            conn.execute("ALTER TABLE cards ADD COLUMN national_dex INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_national_dex ON cards (national_dex)")
        except sqlite3.OperationalError:
            pass

        if not _column_exists(conn, "cards", "types"):
            conn.execute("ALTER TABLE cards ADD COLUMN types TEXT")

        try:
            conn.execute("ALTER TABLE binders ADD COLUMN type TEXT DEFAULT 'custom'")
        except sqlite3.OperationalError:
            pass
        conn.execute("UPDATE binders SET type = 'custom' WHERE type IS NULL OR type = ''")

        if not _column_exists(conn, "binders", "inner_color"):
            conn.execute("ALTER TABLE binders ADD COLUMN inner_color TEXT")
        conn.execute("UPDATE binders SET inner_color = color WHERE inner_color IS NULL OR inner_color = ''")

        if _table_exists(conn, "favorite_sets") and not _column_exists(conn, "favorite_sets", "sort_order"):
            conn.execute("ALTER TABLE favorite_sets ADD COLUMN sort_order INTEGER DEFAULT 0")

        if not _column_exists(conn, "binders", "panel_color"):
            conn.execute("ALTER TABLE binders ADD COLUMN panel_color TEXT")
        conn.execute("UPDATE binders SET panel_color = '#16141d' WHERE panel_color IS NULL OR panel_color = ''")

        if _table_exists(conn, "binder_slots") and not _column_exists(conn, "binder_slots", "custom_image_url"):
            conn.execute("ALTER TABLE binder_slots ADD COLUMN custom_image_url TEXT")
        if _table_exists(conn, "binder_slots") and not _column_exists(conn, "binder_slots", "slot_span"):
            conn.execute("ALTER TABLE binder_slots ADD COLUMN slot_span INTEGER DEFAULT 1")

        if _table_exists(conn, "wishlist_board_cards") and not _column_exists(conn, "wishlist_board_cards", "sort_order"):
            conn.execute("ALTER TABLE wishlist_board_cards ADD COLUMN sort_order INTEGER DEFAULT 0")

        _migrate_to_multiuser(conn)

        if not _column_exists(conn, "users", "username"):
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (username)")
        
        if not _column_exists(conn, "users", "avatar_pokemon_id"):
            conn.execute("ALTER TABLE users ADD COLUMN avatar_pokemon_id INTEGER")
            
        if not _column_exists(conn, "users", "is_admin"):
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            conn.execute("UPDATE users SET is_admin = 1 WHERE id = 1")
            print("[Database] 'is_admin' column added to users. User ID 1 granted admin rights.")

        check = conn.execute("SELECT COUNT(*) AS c FROM cards WHERE national_dex IS NOT NULL").fetchone()
        if check and check["c"] == 0:
            count = conn.execute("SELECT COUNT(*) AS c FROM cards").fetchone()
            if count and count["c"] > 0:
                conn.execute("UPDATE sets SET last_synced = NULL")
                print("[Database] Database reset to populate National Pokédex data.")


# ---------- Users ----------

def create_user(conn, email: str, username: str, password_hash: str, is_admin: int = 0):
    import datetime
    now = datetime.datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO users (email, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
        (email.strip().lower(), username.strip(), password_hash, is_admin, now),
    )
    return cursor.lastrowid


def get_user_by_email(conn, email: str):
    return conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()


def get_user_by_username(conn, username: str):
    return conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()


def get_user_by_id(conn, user_id: int):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def count_users(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]


def claim_legacy_data(conn, user_id: int):
    for table, id_col in (("collection", "card_id"), ("wishlist", "card_id"), ("favorite_sets", "set_id")):
        legacy_name = f"{table}_legacy"
        if _table_exists(conn, legacy_name):
            rows = conn.execute(f"SELECT {id_col} FROM {legacy_name}").fetchall()
            for r in rows:
                conn.execute(
                    f"INSERT OR IGNORE INTO {table} (user_id, {id_col}) VALUES (?, ?)",
                    (user_id, r[id_col]),
                )
            conn.execute(f"DROP TABLE {legacy_name}")

    conn.execute("UPDATE binders SET user_id = ? WHERE user_id IS NULL", (user_id,))


def upsert_set(conn, set_data: dict):
    conn.execute(
        """
        INSERT INTO sets (id, name, series, release_date, logo_url, symbol_url, total_cards, last_synced)
        VALUES (:id, :name, :series, :release_date, :logo_url, :symbol_url, :total_cards, :last_synced)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            series=excluded.series,
            release_date=excluded.release_date,
            logo_url=excluded.logo_url,
            symbol_url=excluded.symbol_url,
            total_cards=excluded.total_cards,
            last_synced=COALESCE(excluded.last_synced, sets.last_synced)
        """,
        set_data,
    )


def upsert_card(conn, card_data: dict):
    conn.execute(
        """
        INSERT INTO cards (id, set_id, name, card_number, rarity, image_small, image_large,
                            price_market, price_low, price_mid, price_high, currency, last_updated, national_dex, types)
        VALUES (:id, :set_id, :name, :card_number, :rarity, :image_small, :image_large,
                :price_market, :price_low, :price_mid, :price_high, :currency, :last_updated, :national_dex, :types)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            card_number=excluded.card_number,
            rarity=COALESCE(excluded.rarity, cards.rarity),
            image_small=COALESCE(excluded.image_small, cards.image_small),
            image_large=COALESCE(excluded.image_large, cards.image_large),
            price_market=COALESCE(excluded.price_market, cards.price_market),
            price_low=COALESCE(excluded.price_low, cards.price_low),
            price_mid=COALESCE(excluded.price_mid, cards.price_mid),
            price_high=COALESCE(excluded.price_high, cards.price_high),
            currency=COALESCE(excluded.currency, cards.currency),
            last_updated=COALESCE(excluded.last_updated, cards.last_updated),
            national_dex=COALESCE(excluded.national_dex, cards.national_dex),
            types=COALESCE(excluded.types, cards.types)
        """,
        card_data,
    )


def mark_set_synced(conn, set_id: str, timestamp: str):
    conn.execute("UPDATE sets SET last_synced = ? WHERE id = ?", (timestamp, set_id))


def get_all_sets(conn, user_id=None):
    return conn.execute(
        """SELECT *,
           (SELECT 1 FROM favorite_sets WHERE set_id = sets.id AND user_id = ?) AS is_favorite,
           (SELECT sort_order FROM favorite_sets WHERE set_id = sets.id AND user_id = ?) AS fav_sort_order
           FROM sets ORDER BY release_date DESC""",
        (user_id, user_id),
    ).fetchall()


def reorder_favorite_sets(conn, user_id: int, set_ids: list):
    for idx, set_id in enumerate(set_ids):
        conn.execute(
            "UPDATE favorite_sets SET sort_order = ? WHERE user_id = ? AND set_id = ?",
            (idx, user_id, set_id),
        )


def get_sets_needing_refresh(conn, cutoff_iso: str):
    return conn.execute(
        "SELECT * FROM sets WHERE last_synced IS NOT NULL AND last_synced < ? ORDER BY last_synced ASC",
        (cutoff_iso,),
    ).fetchall()


def get_set(conn, set_id: str):
    return conn.execute("SELECT * FROM sets WHERE id = ?", (set_id,)).fetchone()


def get_cards_for_set(conn, set_id: str, rarity: str | None = None, user_id=None, card_type: str | None = None):
    query = """SELECT *,
           (SELECT 1 FROM collection WHERE card_id = cards.id AND user_id = ?) AS is_owned,
           (SELECT 1 FROM wishlist WHERE card_id = cards.id AND user_id = ?) AS is_wished
           FROM cards WHERE set_id = ?"""
    params = [user_id, user_id, set_id]
    if rarity:
        query += " AND rarity = ?"
        params.append(rarity)
    if card_type:
        query += " AND (',' || types || ',') LIKE ?"
        params.append(f"%,{card_type},%")
    query += " ORDER BY price_market IS NULL, price_market DESC"
    return conn.execute(query, params).fetchall()


def get_rarities_for_set(conn, set_id: str):
    rows = conn.execute(
        "SELECT DISTINCT rarity FROM cards WHERE set_id = ? AND rarity IS NOT NULL ORDER BY rarity",
        (set_id,),
    ).fetchall()
    return [r["rarity"] for r in rows]


def search_cards_global(conn, name=None, rarity=None, pokedex_number=None, user_id=None, card_type=None):
    query = """
        SELECT cards.*, sets.name AS set_name, sets.release_date,
               (SELECT 1 FROM collection WHERE card_id = cards.id AND user_id = ?) AS is_owned,
               (SELECT 1 FROM wishlist WHERE card_id = cards.id AND user_id = ?) AS is_wished
        FROM cards
        JOIN sets ON cards.set_id = sets.id
        WHERE 1=1
    """
    params = [user_id, user_id]
    if name:
        query += " AND cards.name LIKE ?"
        params.append(f"%{name}%")
    if rarity:
        query += " AND cards.rarity = ?"
        params.append(rarity)
    if pokedex_number:
        query += " AND cards.national_dex = ?"
        params.append(pokedex_number)
    if card_type:
        query += " AND (',' || cards.types || ',') LIKE ?"
        params.append(f"%,{card_type},%")

    query += " ORDER BY sets.release_date DESC, cards.price_market IS NULL, cards.price_market DESC"
    return conn.execute(query, params).fetchall()


def toggle_card_ownership(conn, user_id: int, card_id: str):
    existing = conn.execute(
        "SELECT 1 FROM collection WHERE user_id = ? AND card_id = ?", (user_id, card_id)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM collection WHERE user_id = ? AND card_id = ?", (user_id, card_id))
        return False
    else:
        conn.execute("INSERT INTO collection (user_id, card_id) VALUES (?, ?)", (user_id, card_id))
        return True


def toggle_wishlist_ownership(conn, user_id: int, card_id: str):
    existing = conn.execute(
        "SELECT 1 FROM wishlist WHERE user_id = ? AND card_id = ?", (user_id, card_id)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM wishlist WHERE user_id = ? AND card_id = ?", (user_id, card_id))
        conn.execute(
            """DELETE FROM wishlist_board_cards
               WHERE card_id = ? AND board_id IN (SELECT id FROM wishlist_boards WHERE user_id = ?)""",
            (card_id, user_id)
        )
        return False
    else:
        conn.execute("INSERT INTO wishlist (user_id, card_id) VALUES (?, ?)", (user_id, card_id))
        return True


def toggle_set_favorite(conn, user_id: int, set_id: str):
    existing = conn.execute(
        "SELECT 1 FROM favorite_sets WHERE user_id = ? AND set_id = ?", (user_id, set_id)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM favorite_sets WHERE user_id = ? AND set_id = ?", (user_id, set_id))
        return False
    else:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM favorite_sets WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO favorite_sets (user_id, set_id, sort_order) VALUES (?, ?, ?)",
            (user_id, set_id, next_order),
        )
        return True


def get_user_collection(conn, user_id: int):
    return conn.execute(
        """SELECT cards.*, sets.name AS set_name, sets.release_date
           FROM collection
           JOIN cards ON collection.card_id = cards.id
           JOIN sets ON cards.set_id = sets.id
           WHERE collection.user_id = ?
           ORDER BY sets.release_date DESC, cards.price_market IS NULL, cards.price_market DESC""",
        (user_id,),
    ).fetchall()


def get_user_wishlist(conn, user_id: int):
    return conn.execute(
        """SELECT cards.*, sets.name AS set_name, sets.release_date
           FROM wishlist
           JOIN cards ON wishlist.card_id = cards.id
           JOIN sets ON cards.set_id = sets.id
           WHERE wishlist.user_id = ?
           ORDER BY sets.release_date DESC, cards.price_market IS NULL, cards.price_market DESC""",
        (user_id,),
    ).fetchall()


def get_all_global_rarities(conn, name=None):
    if name:
        rows = conn.execute(
            "SELECT DISTINCT rarity FROM cards WHERE rarity IS NOT NULL AND name LIKE ? ORDER BY rarity",
            (f"%{name}%",)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT rarity FROM cards WHERE rarity IS NOT NULL ORDER BY rarity"
        ).fetchall()
    return [r["rarity"] for r in rows]


def get_all_global_types(conn):
    rows = conn.execute("SELECT DISTINCT types FROM cards WHERE types IS NOT NULL AND types != ''").fetchall()
    seen = set()
    for r in rows:
        for t in r["types"].split(","):
            t = t.strip()
            if t:
                seen.add(t)
    return sorted(seen)


def create_binder(conn, user_id: int, name, color, rows, cols, b_type, inner_color=None, panel_color=None):
    cursor = conn.execute(
        "INSERT INTO binders (user_id, name, color, inner_color, panel_color, rows, cols, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, name, color, inner_color or color, panel_color or "#16141d", rows, cols, b_type)
    )
    return cursor.lastrowid


def update_binder(conn, binder_id: int, user_id: int, name=None, color=None, inner_color=None, panel_color=None):
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if color is not None:
        fields.append("color = ?")
        params.append(color)
    if inner_color is not None:
        fields.append("inner_color = ?")
        params.append(inner_color)
    if panel_color is not None:
        fields.append("panel_color = ?")
        params.append(panel_color)
    if not fields:
        return False
    params.extend([binder_id, user_id])
    cursor = conn.execute(
        f"UPDATE binders SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
        params,
    )
    return cursor.rowcount > 0


def get_all_binders(conn, user_id: int):
    return conn.execute(
        "SELECT * FROM binders WHERE user_id = ? ORDER BY id ASC", (user_id,)
    ).fetchall()


def get_binder(conn, binder_id: int, user_id: int):
    return conn.execute(
        "SELECT * FROM binders WHERE id = ? AND user_id = ?", (binder_id, user_id)
    ).fetchone()


def delete_binder(conn, binder_id: int, user_id: int):
    conn.execute(
        "DELETE FROM binder_slots WHERE binder_id = ? AND binder_id IN (SELECT id FROM binders WHERE id = ? AND user_id = ?)",
        (binder_id, binder_id, user_id),
    )
    conn.execute("DELETE FROM binders WHERE id = ? AND user_id = ?", (binder_id, user_id))


def get_binder_slots(conn, binder_id: int):
    return conn.execute(
        """SELECT binder_slots.*, cards.name, cards.image_small, cards.image_large, cards.price_market, cards.currency
           FROM binder_slots
           LEFT JOIN cards ON binder_slots.card_id = cards.id
           WHERE binder_slots.binder_id = ?""",
        (binder_id,)
    ).fetchall()


def set_binder_slot(conn, binder_id: int, slot_number: int, card_id: str | None, custom_image_url: str | None = None, slot_span: int = 1):
    conn.execute("DELETE FROM binder_slots WHERE binder_id = ? AND slot_number = ?", (binder_id, slot_number))
    if card_id or custom_image_url:
        conn.execute(
            "INSERT INTO binder_slots (binder_id, slot_number, card_id, custom_image_url, slot_span) VALUES (?, ?, ?, ?, ?)",
            (binder_id, slot_number, card_id if card_id else None, custom_image_url if custom_image_url else None, slot_span)
        )


def get_uncategorized_wishlist(conn, user_id: int):
    return conn.execute(
        """SELECT cards.*, sets.name AS set_name, sets.release_date
           FROM wishlist
           JOIN cards ON wishlist.card_id = cards.id
           JOIN sets ON cards.set_id = sets.id
           WHERE wishlist.user_id = ?
           ORDER BY sets.release_date DESC, cards.price_market IS NULL, cards.price_market DESC""",
        (user_id,),
    ).fetchall()


def get_wishlist_boards(conn, user_id: int):
    return conn.execute(
        """SELECT wb.*, (SELECT COUNT(*) FROM wishlist_board_cards WHERE board_id = wb.id) AS card_count
           FROM wishlist_boards wb
           WHERE wb.user_id = ?
           ORDER BY wb.sort_order ASC, wb.id ASC""",
        (user_id,)
    ).fetchall()


def get_wishlist_board(conn, board_id: int, user_id: int):
    return conn.execute(
        "SELECT * FROM wishlist_boards WHERE id = ? AND user_id = ?", (board_id, user_id)
    ).fetchone()


def create_wishlist_board(conn, user_id: int, name: str, color: str):
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM wishlist_boards WHERE user_id = ?", (user_id,)
    ).fetchone()["n"]
    cursor = conn.execute(
        "INSERT INTO wishlist_boards (user_id, name, color, sort_order) VALUES (?, ?, ?, ?)",
        (user_id, name, color, next_order)
    )
    return cursor.lastrowid


def reorder_wishlist_boards(conn, user_id: int, board_ids: list):
    for idx, board_id in enumerate(board_ids):
        conn.execute(
            "UPDATE wishlist_boards SET sort_order = ? WHERE user_id = ? AND id = ?",
            (idx, user_id, board_id),
        )


def reorder_board_cards(conn, board_id: int, card_ids: list):
    for idx, card_id in enumerate(card_ids):
        conn.execute(
            "UPDATE wishlist_board_cards SET sort_order = ? WHERE board_id = ? AND card_id = ?",
            (idx, board_id, card_id),
        )


def update_wishlist_board(conn, board_id: int, user_id: int, name=None, color=None):
    fields, params = [], []
    if name is not None:
        fields.append("name = ?"); params.append(name)
    if color is not None:
        fields.append("color = ?"); params.append(color)
    if not fields:
        return False
    params.extend([board_id, user_id])
    cursor = conn.execute(
        f"UPDATE wishlist_boards SET {', '.join(fields)} WHERE id = ? AND user_id = ?", params
    )
    return cursor.rowcount > 0


def delete_wishlist_board(conn, board_id: int, user_id: int):
    conn.execute(
        """DELETE FROM wishlist_board_cards
           WHERE board_id = ? AND board_id IN (SELECT id FROM wishlist_boards WHERE id = ? AND user_id = ?)""",
        (board_id, board_id, user_id)
    )
    conn.execute("DELETE FROM wishlist_boards WHERE id = ? AND user_id = ?", (board_id, user_id))


def get_wishlist_board_cards(conn, board_id: int):
    return conn.execute(
        """SELECT cards.*, sets.name AS set_name, sets.release_date
           FROM wishlist_board_cards wbc
           JOIN cards ON wbc.card_id = cards.id
           JOIN sets ON cards.set_id = sets.id
           WHERE wbc.board_id = ?
           ORDER BY wbc.sort_order ASC, sets.release_date DESC""",
        (board_id,)
    ).fetchall()


def add_card_to_board(conn, board_id: int, card_id: str):
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM wishlist_board_cards WHERE board_id = ?", (board_id,)
    ).fetchone()["n"]
    conn.execute(
        "INSERT OR IGNORE INTO wishlist_board_cards (board_id, card_id, sort_order) VALUES (?, ?, ?)",
        (board_id, card_id, next_order)
    )


def remove_card_from_board(conn, board_id: int, card_id: str):
    conn.execute("DELETE FROM wishlist_board_cards WHERE board_id = ? AND card_id = ?", (board_id, card_id))