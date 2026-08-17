# Pokyudex

Pokyudex is a personal web application for browsing Pokémon TCG expansions and viewing all the cards in each set.

Cards are displayed with their images, rarity, and available market price, and can be sorted by price and filtered by rarity such as **Illustration Rare** and **Special Illustration Rare**.

The application uses the [Pokémon TCG API](https://docs.pokemontcg.io/) to retrieve card and pricing information and stores downloaded data in a local SQLite database for faster subsequent access.

## Motivation

The goal of Pokyudex is to provide a simple and fast way to browse Pokémon TCG expansions and immediately identify the most valuable cards in a set.

Instead of making external API requests every time a set is opened, Pokyudex downloads the cards the first time they are requested and stores them locally in a SQLite database.

This provides two main advantages:

* Faster loading when revisiting previously downloaded sets.
* Fewer requests to the external API.

The project was also created as a personal programming project to experiment with **Python, Flask, SQLite, APIs, and frontend web development**.

## Quick Start

### Requirements

* Python 3
* pip
* Internet connection
* A Pokémon TCG API key is recommended but optional

### Installation

Clone the repository and enter the project directory:

```bash
git clone <repository-url>
cd pokemon-tracker
```

Create a Python virtual environment:

```bash
cd backend
python3 -m venv venv
```

Activate the virtual environment.

**Linux / macOS:**

```bash
source venv/bin/activate
```

**Windows:**

```bash
venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### API Key

An API key is optional. The application works without one, but the Pokémon TCG API has lower request limits when no key is provided.

For regular use, a free API key can be obtained from the [Pokémon TCG Developer Portal](https://dev.pokemontcg.io/).

From the project root:

```bash
cd ..
cp .env.example .env
```

Then add your API key to `.env`:

```env
POKEMONTCG_API_KEY=your_api_key_here
```

The application will still work if the key is left empty.

### Start the Application

Run the Flask server:

```bash
cd backend
python app.py
```

Then open:

```text
http://localhost:5000
```

## Usage

After starting the application, open it in a web browser and select a Pokémon TCG expansion.

For each expansion, Pokyudex allows you to:

* View all cards in the set.
* Sort cards by price from highest to lowest.
* Filter cards by rarity.
* View card images and pricing information.
* Update prices for an already downloaded set.

### Data and Caching

When an expansion is opened for the first time, Pokyudex downloads its cards from the Pokémon TCG API and stores them in:

```text
data/pokemon.db
```

The database is created automatically.

When the same expansion is opened again, the application loads the data from the local database instead of making new API requests.

To update prices for an existing set, use the **Update Prices** button on the set page.

### Pricing

Pokyudex uses the pricing information provided through the Pokémon TCG API.

The price priority is:

1. **CardMarket** — EUR
2. **TCGPlayer** — USD

If CardMarket pricing is unavailable for a card, TCGPlayer pricing is used instead.

Prices are not real-time. The pricing data is generally updated approximately once per day by the respective services.

Some cards may not have available pricing information. In these cases, the application displays `N/A`.

## Hosting

The Flask server listens on `0.0.0.0`, allowing the application to be accessed from other devices on the same local network.

For example:

```text
http://SERVER-IP:5000
```

For a more stable Linux deployment, Gunicorn can be used together with systemd.

Install Gunicorn:

```bash
pip install gunicorn
```

Start the application:

```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

Example systemd service:

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

Save the service as:

```text
/etc/systemd/system/pokyudex.service
```

Then enable and start it:

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

## Contributing

Contributions are welcome.

If you would like to contribute to Pokyudex:

1. Fork the repository.
2. Create a new branch for your changes.
3. Make your changes and test them locally.
4. Commit your changes with a clear commit message.
5. Open a Pull Request describing what you changed.

When contributing, please try to keep the existing project structure and coding style consistent.

If the Pokémon TCG API changes its response format, the API-related normalization logic can be found in `backend/pokemon_api.py`, particularly in the `normalize_set` and `normalize_card` functions.

## Future Improvements

Some features that could be added in the future include:

* Automatic scheduled price updates.
* A favorites page for frequently viewed sets.
* User card collections.
* Price history and charts.
* More advanced card filtering.
* Additional pricing sources.
* Near-real-time pricing through alternative APIs.

## Disclaimer

Pokyudex is a personal project and is not affiliated with, endorsed by, or sponsored by **The Pokémon Company**, **Nintendo**, **Creatures Inc.**, **GAME FREAK**, **CardMarket**, or **TCGPlayer**.

Pokémon and Pokémon TCG are trademarks of their respective owners.
