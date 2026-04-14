FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System libraries: WeasyPrint (Cairo/Pango) + build toolchain
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libcairo-gobject2 \
        libffi-dev \
        libgdk-pixbuf-2.0-0 \
        libharfbuzz0b \
        libharfbuzz-icu0 \
        shared-mime-info \
        fonts-noto \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

# Upgrade pip then install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Download spaCy English model used by the NLP service
RUN python -m spacy download en_core_web_md

COPY . /app
