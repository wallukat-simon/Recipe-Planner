FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY *.py /app/

# Install build tools and git
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && mkdir /app/h2media-graph

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
