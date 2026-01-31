# 1. Python image fayyadami
FROM python:3.13-slim

# 2. Tesseract fi dependencies biroo fe'i
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Work directory uumi
WORKDIR /app

# 4. Faayiloota requirements copy godhi
COPY requirements.txt .

# 5. Libraries Python fe'i
RUN pip install --no-cache-dir -r requirements.txt

# 6. Koodii kee hunda copy godhi
COPY . .

# 7. Foldaroota barbaachisan uumi
RUN mkdir -p /tmp/uploads /tmp/extracted_images /tmp/cards

# 8. Gunicorn fayyadamii jalqabsiisi
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
