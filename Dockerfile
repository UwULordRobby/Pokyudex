# Usiamo un'immagine Python leggera
FROM python:3.10-slim

# Impostiamo la cartella di lavoro
WORKDIR /app

# Copiamo prima i requisiti e li installiamo (ottimizza la cache di Docker)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamo tutto il resto del progetto (sia backend che frontend)
COPY . .

# Esponiamo la porta esatta che Tailscale sta cercando
EXPOSE 5000

# Avviamo la tua applicazione Flask
CMD ["python", "backend/app.py"]