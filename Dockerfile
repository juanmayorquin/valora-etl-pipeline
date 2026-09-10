FROM python:3.11-slim

# PYTHONUNBUFFERED: sin esto los logs quedan en el buffer y `docker compose logs` no
#   muestra nada hasta que el proceso termina - inservible para un scraper de horas.
# PYTHONIOENCODING: la salida lleva acentos y el símbolo m²; sin forzar UTF-8 la escritura
#   al stream falla o degrada según el locale del contenedor.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Se copia sólo requirements primero para que la capa de instalación (la cara: Chromium
# pesa cientos de MB) se reutilice mientras las dependencias no cambien.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY src/ ./src/

ENV HEADLESS=true

# Sin argumentos corre el pipeline completo. Cada etapa se invoca por separado desde
# docker-compose (servicios `scraper` y `transform`).
CMD ["python", "src/extract.py"]
