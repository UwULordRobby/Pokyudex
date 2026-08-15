# Pokyudex

A personal web application for browsing Pokémon TCG expansions and quickly viewing all the cards in each set, sorted by price from highest to lowest, with rarity filters such as **Illustration Rare**, **Special Illustration Rare**, and more.

## Features

* Browse Pokémon TCG expansions.
* View all cards contained in a set.
* Sort cards by price, from highest to lowest.
* Filter cards by rarity.
* Display card images and pricing information.
* Use **CardMarket prices in EUR** whenever available.
* Fall back to **TCGPlayer prices in USD** when CardMarket data is unavailable.
* Store downloaded sets locally using **SQLite**.
* Avoid unnecessary API requests by caching downloaded data locally.
* Manually update prices for previously downloaded sets.

## Motivation

Pokyudex was created as a personal project to make browsing and tracking Pokémon TCG cards easier.

The main goal is to have a simple interface where it is possible to open an expansion and immediately see which cards are the most valuable, without having to manually check individual cards or external websites.

The application also uses a local database to reduce the number of external API requests and make subsequent visits to already downloaded sets much faster.

## How It Works

Pokyudex uses the [Pokémon TCG API](https://docs.pokemontcg.io/) to retrieve card, set, image, rarity, and pricing information.

When a set is opened for the first time:

1. Pokyudex requests the set's cards from the Pokémon TCG API.
2. The cards and their relevant information are stored in a local SQLite database.
3. The application displays the cards using the locally stored data.

When the same set is opened again, the application reads the data directly from SQLite instead of making new API requests.

This makes subsequent visits significantly faster and reduces unnecessary requests to the external API.

Prices can be manually refreshed using the **"Update Prices"** button on the set page.

### Pricing Data

Prices are provided by the Pokémon TCG API and are based on:

* **CardMarket (EUR)** when available.
* **TCGPlayer (USD)** as a fallback.

Prices are updated by the respective services approximately once per day. They are therefore **not real-time prices**, but they provide a free and convenient way to track card values without requiring a paid pricing API or managing API credits.

## Quick Start

### 1. Clone the repository

```bash
git clone <repository-url>
cd pokemon-tracker
```

### 2. Create a virtual environment

It is recommended to use a Python virtual environment.

```bash
cd backend
python3 -m venv venv
```

Activate it with:

**Linux / macOS**

```bash
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the API key

An API key is optional.

Without a key, Pokyudex still works, but the Pokémon TCG API has significantly lower request limits.

For regular use, you can get a free API key from the [Pokémon TCG Developer Portal](https://dev.pokemontcg.io/).

From the project root:

```bash
cd ..
cp .env.example .env
```

Then add your API key to `.env`:

```env
POKEMONTCG_API_KEY=your_api_key_here
```

If you leave it empty, the application will still work.

### 5. Start the server

```bash
cd backend
python app.py
```

The application will be available at:

```text
http://localhost:5000
```

## Usage

Once the server is running, open `http://localhost:5000` in your browser.

From the main page you can:

1. Select a Pokémon TCG expansion.
2. Browse all cards in the set.
3. Sort cards by price.
4. Filter cards by rarity.
5. Refresh prices using the **"Update Prices"** button.

### Local Database

The SQLite database is created automatically when the application is first started:

```text
data/pokemon.db
```

Downloaded sets are stored locally, so opening the same set again does not require another API request.

## Hosting on a Local Server

The Flask server is already configured to listen on `0.0.0.0`, making it accessible from other devices on the same local network.

For example:

```text
http://SERVER-IP:5000
```

For a more reliable deployment on Linux, **Gunicorn** and **systemd** can be used to automatically start and restart the application.

### Gunicorn

Install Gunicorn:

```bash
pip install gunicorn
```

Then start the application with:

```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

### systemd

Example service file:

```ini
[Unit]
Description=Pokyudex
After=network.target

[Service]
WorkingDirectory=/path/to/pokemon-tracker/backend
Environment="PATH=/path/to/pokemon-tracker/backend/venv/bin"
ExecStart=/path/to/pokemon-tracker/backend/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Save it as:

```text
/etc/systemd/system/pokyudex.service
```

Then enable and start the service:

```bash
sudo systemctl enable --now pokyudex
```

## Project Structure

```text
pokemon-tracker/
├── .env.example
├── README.md
├── backend/
│   ├── app.py              # Flask routes and frontend service
│   ├── config.py           # Application configuration
│   ├── db.py               # SQLite database access
│   ├── pokemon_api.py      # Pokémon TCG API integration
│   └── requirements.txt
├── data/
│   └── pokemon.db          # Created automatically
└── frontend/
    ├── index.html          # Main page and expansion selection
    ├── set.html            # Card grid and rarity filters
    ├── app.js
    └── style.css
```

## Price Information

Each card displays its available price using the following priority:

1. **CardMarket — EUR**
2. **TCGPlayer — USD**

The currency symbol is displayed according to the source used for each card.

Some very new or niche cards may not have pricing information yet. In those cases, Pokyudex displays:

```text
N/A
```

### Future Pricing Improvements

For more accurate or frequently updated pricing data, a paid API could be integrated in the future, potentially providing:

* Near-real-time prices.
* Historical price data.
* eBay pricing information.
* Additional marketplaces.

The API integration is intentionally isolated in `pokemon_api.py`, making it possible to replace the pricing provider without significantly modifying the rest of the application.

## Future Improvements

Possible future additions include:

* [ ] Automatic scheduled price updates using cron or another scheduler.
* [ ] A **Favorites** page for frequently viewed sets.
* [ ] User-defined collections or card tracking.
* [ ] Price history charts.
* [ ] More detailed card filtering.
* [ ] Additional pricing sources.
* [ ] Improved handling of changes to the Pokémon TCG API response format.

## Disclaimer

Pokyudex is a personal project and is not affiliated with, endorsed by, or sponsored by **The Pokémon Company**, **Nintendo**, **Creatures Inc.**, **GAME FREAK**, **CardMarket**, or **TCGPlayer**.

Pokémon and Pokémon TCG are trademarks of their respective owners.
