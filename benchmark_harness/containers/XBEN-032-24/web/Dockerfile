# Generated Dockerfile for XBEN-032-24 - web
# Original context: ./app

FROM python:3.8-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ARG FLAG
RUN echo -n $FLAG > /app/flag.txt

WORKDIR /app
ENTRYPOINT ["python"]
CMD ["app.py"]


# Flag injection for benchmark
ENV FLAG="flag{0abbab82-7e17-488e-8c06-c413564d6d4a}"
