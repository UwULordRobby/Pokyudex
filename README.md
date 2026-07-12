# PokéPrezzi

App web personale per sfogliare le espansioni Pokémon e vedere subito tutte le
carte ordinate dal prezzo più alto al più basso, con filtro per rarità
(Illustration Rare, Special Illustration Rare, ecc).

## Come funziona

- I dati (carte, immagini, prezzi, rarità) arrivano dalla
  [Pokémon TCG API](https://docs.pokemontcg.io/) (`api.pokemontcg.io`), gratuita.
- I prezzi inclusi sono quelli di **CardMarket** (in EUR, quando disponibili
  per la carta) o in alternativa quelli di **TCGPlayer** (in USD). Vengono
  aggiornati dal loro sistema circa una volta al giorno: non sono prezzi
  "live" al secondo, ma sono gratis e non richiedono di gestire crediti.
- La prima volta che apri un'espansione, l'app scarica tutte le sue carte
  dall'API e le salva in un database locale SQLite (`data/pokemon.db`).
- Le visite successive alla stessa espansione leggono dal database locale:
  velocissimo, zero chiamate esterne.
- Per aggiornare i prezzi di un set già scaricato, usa il bottone
  "Aggiorna prezzi" nella pagina del set.

## Setup

1. **(Opzionale ma consigliata) Ottieni una API key gratuita**
   Senza key l'app funziona comunque, ma con limiti di richieste piuttosto
   bassi (utile giusto per provarla). Per un uso regolare, registrati gratis
   su https://dev.pokemontcg.io per una key con limiti molto più alti.

2. **Installa le dipendenze Python** (consigliato un virtualenv)
   ```bash
   cd pokemon-tracker/backend
   python3 -m venv venv
   source venv/bin/activate        # su Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configura (facoltativo) la API key**
   ```bash
   cd ..
   cp .env.example .env
   ```
   Se hai una key, incollala in `.env` dopo `POKEMONTCG_API_KEY=`. Se la lasci
   vuota l'app funziona lo stesso.

4. **Avvia il server**
   ```bash
   cd backend
   python app.py
   ```
   Apri il browser su http://localhost:5000

## Hosting sul tuo server secondario

Il server Flask è già configurato per ascoltare su `0.0.0.0`, quindi è
raggiungibile da altri dispositivi della tua rete locale all'indirizzo
`http://IP-DEL-SERVER:5000`.

Per un uso più stabile (avvio automatico, riavvio in caso di crash), su Linux
ti consiglio di usare **gunicorn** + un servizio **systemd**:

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

Esempio di unit systemd (`/etc/systemd/system/pokeprezzi.service`):
```ini
[Unit]
Description=PokéPrezzi
After=network.target

[Service]
WorkingDirectory=/percorso/pokemon-tracker/backend
Environment="PATH=/percorso/pokemon-tracker/backend/venv/bin"
ExecStart=/percorso/pokemon-tracker/backend/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```
Poi: `sudo systemctl enable --now pokeprezzi`.

## Struttura del progetto

```
pokemon-tracker/
├── .env.example
├── README.md
├── backend/
│   ├── app.py            # rotte Flask (API + servizio frontend)
│   ├── config.py         # configurazione (API key, DB path, host/porta)
│   ├── db.py             # accesso al database SQLite locale
│   ├── pokemon_api.py    # chiamate alla Pokémon TCG API
│   └── requirements.txt
├── data/
│   └── pokemon.db        # creato automaticamente al primo avvio
└── frontend/
    ├── index.html         # pagina principale: pulsanti espansioni
    ├── set.html           # grid carte + filtri rarità
    ├── app.js
    └── style.css
```

## Note sui prezzi

- Ogni carta mostra il prezzo in EUR (CardMarket) quando disponibile,
  altrimenti in USD (TCGPlayer): il simbolo di valuta nel prezzo cambia di
  conseguenza carta per carta.
- Alcune carte molto nuove o molto di nicchia potrebbero non avere ancora
  prezzo disponibile: in quel caso viene mostrato "n/d".
- Se vuoi prezzi più aggiornati/precisi in futuro (near-real-time, storico
  prezzi, dati eBay), l'alternativa è un'API a pagamento come
  PokemonPriceTracker o JustTCG — il codice in `pokemon_api.py` è isolato
  apposta per poterla sostituire senza toccare il resto dell'app.

## Possibili miglioramenti futuri

- Job schedulato (cron) per aggiornare automaticamente i prezzi dei set che
  segui più spesso, invece di farlo manualmente.
- Pagina "i miei set preferiti" per non dover scorrere tutte le espansioni.
- Se lo schema dei campi restituiti dall'API cambia leggermente, controlla
  `pokemon_api.py` (funzioni `normalize_set` / `normalize_card`).
