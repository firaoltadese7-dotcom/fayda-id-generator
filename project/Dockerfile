FROM python:3.13-slim

# Tesseract fi dabalata barbaachisan fe'uu
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Foldaroota yeroo gabaabaaf fayyadan uumuu
RUN mkdir -p /tmp/uploads /tmp/extracted_images /tmp/cards

# Port Render irratti barbaachisu
EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
