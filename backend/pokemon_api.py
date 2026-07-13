"""
Wrapper minimale per la Pokémon TCG API (api.pokemontcg.io/v2).
Docs: https://docs.pokemontcg.io/
"""
import requests

from config import API_BASE_URL, API_KEY


class PokemonAPIError(Exception):
    pass


def _headers():
    headers = {}
    if API_KEY:
        headers["X-Api-Key"] = API_KEY
    return headers


def fetch_sets() -> list[dict]:
    """Recupera l'elenco di tutte le espansioni disponibili."""
    resp = requests.get(f"{API_BASE_URL}/sets", headers=_headers(), timeout=30)
    if resp.status_code == 429:
        raise PokemonAPIError(
            "Limite di richieste raggiunto. Se non hai ancora una API key gratuita, "
            "registrati su https://dev.pokemontcg.io per limiti più alti."
        )
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_cards_for_set(set_id: str) -> list[dict]:
    """Recupera TUTTE le carte di un'espansione con paginazione automatica."""
    all_cards = []
    page = 1
    page_size = 250
    while True:
        params = {"q": f"set.id:{set_id}", "page": page, "pageSize": page_size}
        resp = requests.get(f"{API_BASE_URL}/cards", headers=_headers(), params=params, timeout=60)
        if resp.status_code == 429:
            raise PokemonAPIError("Limite di richieste raggiunto.")
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data", [])
        all_cards.extend(batch)

        total_count = payload.get("totalCount", len(all_cards))
        if len(batch) < page_size or len(all_cards) >= total_count:
            break
        page += 1

    return all_cards


# ---------- NUOVI METODI: Ricerca Live di Emergenza ----------

def fetch_cards_by_pokedex(pokedex_number: int) -> list[dict]:
    """Cerca direttamente sul server Pokémon TCG tutte le carte corrispondenti a un ID Pokédex."""
    params = {"q": f"nationalPokedexNumbers:{pokedex_number}"}
    resp = requests.get(f"{API_BASE_URL}/cards", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_cards_by_name(name: str) -> list[dict]:
    """Cerca direttamente sul server Pokémon TCG le carte corrispondenti a un nome specifico."""
    params = {"q": f"name:\"{name}*\""}
    resp = requests.get(f"{API_BASE_URL}/cards", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def normalize_set(raw: dict) -> dict:
    images = raw.get("images", {}) or {}
    return {
        "id": raw.get("id"),
        "name": raw.get("name", "Set sconosciuto"),
        "series": raw.get("series"),
        "release_date": raw.get("releaseDate"),
        "logo_url": images.get("logo"),
        "symbol_url": images.get("symbol"),
        "total_cards": raw.get("total") or raw.get("printedTotal"),
        "last_synced": None,
    }


_TCGPLAYER_VARIANT_PRIORITY = ["normal", "holofoil", "reverseHolofoil", "1stEditionHolofoil", "1stEditionNormal", "unlimitedHolofoil", "unlimited"]

def _pick_tcgplayer_variant(tcg_prices: dict):
    # Cerca varianti preferite che abbiano ALMENO un prezzo valido valorizzato
    for variant in _TCGPLAYER_VARIANT_PRIORITY:
        v = tcg_prices.get(variant)
        if v and any(v.get(k) is not None for k in ["market", "mid", "low", "high"]):
            return v
    # Recupero di emergenza su qualsiasi altra variante
    for v in tcg_prices.values():
        if v and any(v.get(k) is not None for k in ["market", "mid", "low", "high"]):
            return v
    return None


def normalize_card(raw: dict, set_id: str) -> dict:
    images = raw.get("images", {}) or {}
    cardmarket = raw.get("cardmarket", {}) or {}
    cm_prices = cardmarket.get("prices", {}) or {}
    tcgplayer = raw.get("tcgplayer", {}) or {}
    tcg_prices = tcgplayer.get("prices", {}) or {}

    price_market = price_low = price_mid = price_high = None
    currency = None
    last_updated = None

    if cm_prices:
        price_market = cm_prices.get("trendPrice") or cm_prices.get("averageSellPrice") or cm_prices.get("lowPrice") or cm_prices.get("avg7")
        price_low = cm_prices.get("lowPrice")
        price_mid = cm_prices.get("avg7") or cm_prices.get("trendPrice")
        price_high = cm_prices.get("avg30") or price_market
        if price_market is not None:
            currency = "EUR"
            last_updated = cardmarket.get("updatedAt")

    if currency is None and tcg_prices:
        variant = _pick_tcgplayer_variant(tcg_prices)
        if variant:
            price_market = variant.get("market") or variant.get("mid") or variant.get("low") or variant.get("high")
            price_low = variant.get("low")
            price_mid = variant.get("mid")
            price_high = variant.get("high")
            currency = "USD"
            last_updated = tcgplayer.get("updatedAt")

    card_number = raw.get("number")
    rarity = raw.get("rarity")
    
    if set_id == "blk" and card_number == "171":
        rarity = "Secret Rare"

    dex_list = raw.get("nationalPokedexNumbers")
    national_dex = dex_list[0] if (dex_list and isinstance(dex_list, list)) else None

    raw_types = raw.get("types")
    types = ",".join(raw_types) if (raw_types and isinstance(raw_types, list)) else None

    # Mappatura correttiva delle immagini per il set McDonald's 2018 (mcd18)
    if set_id == "mcd18":
        mcd_mapping = {
            "1": ("sm1", "18"),   # Growlithe
            "2": ("sm1", "28"),   # Psyduck
            "3": ("sm3", "29"),   # Horsea
            "4": ("sm1", "40"),   # Pikachu
            "5": ("sm1", "42"),   # Slowpoke
            "6": ("sm3", "64"),   # Machop
            "7": ("sm3", "72"),   # Cubone
            "8": ("sm5", "81"),   # Magnemite
            "9": ("sm75", "34"),  # Dratini
            "10": ("sm1", "101"), # Chansey
            "11": ("sm5", "104"), # Eevee
            "12": ("sm3", "105")  # Porygon
        }
        if card_number in mcd_mapping:
            orig_set, orig_num = mcd_mapping[card_number]
            image_small = f"https://images.pokemontcg.io/{orig_set}/{orig_num}.png"
            image_large = f"https://images.pokemontcg.io/{orig_set}/{orig_num}_large.png"
        else:
            image_small = images.get("small")
            image_large = images.get("large") or images.get("small")
    else:
        image_small = images.get("small")
        image_large = images.get("large") or images.get("small")

    return {
        "id": raw.get("id"),
        "set_id": set_id,
        "name": raw.get("name", "Carta sconosciuta"),
        "card_number": card_number,
        "rarity": rarity, 
        "image_small": image_small,
        "image_large": image_large,
        "price_market": price_market,
        "price_low": price_low,
        "price_mid": price_mid,
        "price_high": price_high,
        "currency": currency,
        "last_updated": last_updated,
        "national_dex": national_dex,
        "types": types,
    }