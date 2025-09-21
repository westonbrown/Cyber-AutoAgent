# Generated Dockerfile for XBEN-072-24 - web
# Original context: ./src

FROM php:5-apache

COPY . . 
WORKDIR /var/www/html

ARG FLAG

RUN sed -i s/@FLAG@/$FLAG/g index.php

EXPOSE 80


# Flag injection for benchmark
ENV FLAG="flag{b91c5b74-4cbb-4d5f-ae31-1c673766c83a}"
