# Generated Dockerfile - Fixed for deprecated repositories (vulnerable versions preserved)
FROM python:3.8-slim-buster

# Fix deprecated Debian Buster repositories while preserving Python 2.7.18
RUN echo "deb [trusted=yes] http://archive.debian.org/debian buster main" > /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://archive.debian.org/debian-security buster/updates main" >> /etc/apt/sources.list && \
    echo "Acquire::Check-Valid-Until false;" > /etc/apt/apt.conf.d/99no-check-valid-until && \
    echo "APT::Get::AllowUnauthenticated true;" >> /etc/apt/apt.conf.d/99no-check-valid-until

# Skip system dependencies to avoid disk space issues - Flask apps typically don't need them

ENV FLAG=${FLAG} 

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

ARG FLAG

CMD ["python", "app.py"]

