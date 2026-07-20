FROM python:3.12-slim

# Evita file .pyc e abilita output non bufferizzato (log leggibili)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/quotes.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py db.py import_quotes.py export_quotes.py ./

# Il database vive su un volume montato in /data
VOLUME ["/data"]

CMD ["python", "bot.py"]
