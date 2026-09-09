FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY src/ ./src/

ENV HEADLESS=true

CMD ["python", "src/extract.py"]
