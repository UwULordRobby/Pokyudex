"""
Minimal wrapper for the Pokémon TCG API (api.pokemontcg.io/v2).
Docs: https://docs.pokemontcg.io/
"""
import time
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
    """Retrieves the list of all available expansions strictly from the official API."""
    all_sets = []
    page = 1
    page_size = 250
    while True:
        params = {"page": page, "pageSize": page_size}
        resp = requests.get(f"{API_BASE_URL}/sets", headers=_headers(), params=params, timeout=30)
        
        if resp.status_code == 429:
            raise PokemonAPIError("Rate limit reached. If you do not have a free API key yet, register at https://dev.pokemontcg.io.")
        
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data", [])
        all_sets.extend(data)
        
        total_count = payload.get("totalCount", len(all_sets))
        if len(data) < page_size or len(all_sets) >= total_count:
            break
        
        page += 1
        
    return all_sets


def fetch_cards_for_set(set_id: str) -> list[dict]:
    """Retrieves ALL cards for a set with automatic pagination and retry logic."""
    all_cards = []
    raw_fetched = 0
    page = 1
    page_size = 250
    max_retries = 5

    while True:
        params = {"q": f"set.id:{set_id}", "page": page, "pageSize": page_size}
        batch_success = False
        payload = {}
        
        for attempt in range(max_retries):
            try:
                resp = requests.get(f"{API_BASE_URL}/cards", headers=_headers(), params=params, timeout=60)
                
                if resp.status_code == 429:
                    raise PokemonAPIError("Rate limit reached.")
                
                if resp.status_code >= 500:
                    print(f"[API] Server Error {resp.status_code} for set {set_id}. Retrying {attempt + 1}/{max_retries}...")
                    time.sleep(2 ** attempt)
                    continue
                
                resp.raise_for_status()
                payload = resp.json()
                batch_success = True
                break
                
            except requests.exceptions.RequestException as e:
                print(f"[API] Network error for set {set_id}: {e}. Retrying {attempt + 1}/{max_retries}...")
                time.sleep(2 ** attempt)

        if not batch_success:
            raise PokemonAPIError(f"API failed to fetch cards for set {set_id} after {max_retries} retries.")

        batch = payload.get("data", [])
        raw_fetched += len(batch)

        # FILTRO FONDAMENTALE: escludiamo a monte tutte le carte (come le energie base SVE) che non hanno un'immagine ufficiale
        valid_cards = [c for c in batch if c.get("images") and c.get("images").get("small")]
        all_cards.extend(valid_cards)

        total_count = payload.get("totalCount", raw_fetched)
        if len(batch) < page_size or raw_fetched >= total_count:
            break
        page += 1

    return all_cards


# ---------- Emergency Live Search ----------

def fetch_cards_by_pokedex(pokedex_number: int) -> list[dict]:
    try:
        params = {"q": f"nationalPokedexNumbers:{pokedex_number}"}
        resp = requests.get(f"{API_BASE_URL}/cards", headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        # Filtro applicato anche alla ricerca d'emergenza
        return [c for c in data if c.get("images") and c.get("images").get("small")]
    except:
        return []


def fetch_cards_by_name(name: str) -> list[dict]:
    try:
        params = {"q": f"name:\"{name}*\""}
        resp = requests.get(f"{API_BASE_URL}/cards", headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        # Filtro applicato anche alla ricerca d'emergenza
        return [c for c in data if c.get("images") and c.get("images").get("small")]
    except:
        return []


def normalize_set(raw: dict) -> dict:
    images = raw.get("images", {}) or {}
    return {
        "id": raw.get("id"),
        "name": raw.get("name", "Unknown set"),
        "series": raw.get("series"),
        "release_date": raw.get("releaseDate"),
        "logo_url": images.get("logo"),
        "symbol_url": images.get("symbol"),
        "total_cards": raw.get("total") or raw.get("printedTotal"),
        "last_synced": None,
    }


_TCGPLAYER_VARIANT_PRIORITY = ["normal", "holofoil", "reverseHolofoil", "1stEditionHolofoil", "1stEditionNormal", "unlimitedHolofoil", "unlimited"]

def _pick_tcgplayer_variant(tcg_prices: dict):
    for variant in _TCGPLAYER_VARIANT_PRIORITY:
        v = tcg_prices.get(variant)
        if v and any(v.get(k) is not None for k in ["market", "mid", "low", "high"]):
            return v
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

    if set_id == "mcd18":
        mcd_mapping = {
            "1": ("sm1", "18"),   
            "2": ("sm1", "28"),   
            "3": ("sm3", "29"),   
            "4": ("sm1", "40"),   
            "5": ("sm1", "42"),   
            "6": ("sm3", "64"),   
            "7": ("sm3", "72"),   
            "8": ("sm5", "81"),   
            "9": ("sm75", "34"),  
            "10": ("sm1", "101"), 
            "11": ("sm5", "104"), 
            "12": ("sm3", "105")  
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
        "name": raw.get("name", "Unknown card"),
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