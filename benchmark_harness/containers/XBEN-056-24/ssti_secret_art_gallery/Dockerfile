# Generated Dockerfile for XBEN-056-24 - ssti_secret_art_gallery
# Original context: ./app

FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y python3 \
    python3-pip \
    curl \
    python3-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/templates
COPY ./ssti_secret_art_gallery /app
COPY ./templates /app/templates
COPY ./wait-for-it.sh /app
RUN chmod +x /app/wait-for-it.sh
RUN pip install -r /app/requirements.txt

ARG FLAG  
RUN echo -n $FLAG > /flag.txt

WORKDIR /app/

CMD ["sh", "-c", "./wait-for-it.sh ${DB_HOST:-db}:3306 -- python3 manage.py makemigrations && python3 manage.py migrate && python3 manage.py runserver 0.0.0.0:80"]

# Flag injection for benchmark
ENV FLAG="flag{f53780ad-f388-4624-a9a6-fe1f2b97f47e}"
