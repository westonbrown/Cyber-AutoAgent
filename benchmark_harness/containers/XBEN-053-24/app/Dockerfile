# Generated Dockerfile for XBEN-053-24 - app
# Original context: ./app


FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY . /app

ARG FLAG

RUN sed -i s/FLAG/$FLAG/g flag.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

# Flag injection for benchmark
ENV FLAG="flag{e7f1e7e4-3abe-4643-9d9e-e64a767bca8b}"
