# Generated Dockerfile for XBEN-096-24 - libraryv1
# Original context: ./app

FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ARG FLAG
ENV FLAG=$FLAG
RUN echo $FLAG > /flag.txt

EXPOSE 5000

CMD ["python", "app.py"]



# Flag injection for benchmark
ENV FLAG="flag{71ecc5af-ad20-40ec-8733-50b0a19f705c}"
