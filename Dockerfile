# Una sola imagen base y tres targets, para que cada servicio pague sólo lo que usa:
#
#   pipeline    detail, transform, enrich, load, train   (sin navegador)
#   scraper     extract, el único que necesita Chromium   (+ ~1 GB)
#   notebooks   Jupyter Lab con las dependencias de análisis
#
# docker-compose.yml elige el target por servicio. A mano:
#   docker build --target pipeline -t valora-etl:pipeline .

FROM python:3.11-slim AS base

# PYTHONUNBUFFERED: sin esto los logs quedan en el buffer y `docker compose logs` no
#   muestra nada hasta que el proceso termina - inservible para un scraper de horas.
# PYTHONIOENCODING: la salida lleva acentos y el símbolo m²; sin forzar UTF-8 la escritura
#   al stream falla o degrada según el locale del contenedor.
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Se copia sólo requirements primero para que la capa de instalación se reutilice
# mientras las dependencias no cambien.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY web/ ./web/

# --- pipeline -----------------------------------------------------------------
FROM base AS pipeline
CMD ["python", "src/transform.py"]

# --- scraper ------------------------------------------------------------------
# Chromium y sus librerías de sistema pesan más que todo el resto junto, y sólo el
# extract los usa: el resto de las etapas no arrastra ese peso.
FROM base AS scraper
RUN playwright install --with-deps chromium
ENV HEADLESS=true
CMD ["python", "src/extract.py"]

# --- notebooks ----------------------------------------------------------------
# notebooks/, data/ y models/ se montan como volúmenes desde docker-compose: lo que se
# edita en Jupyter queda en tu disco, no dentro del contenedor.
FROM base AS notebooks
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--ServerApp.root_dir=/app/notebooks"]
