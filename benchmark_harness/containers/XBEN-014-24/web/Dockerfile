# Generated Dockerfile for XBEN-014-24 - web
# Original context: ./src

FROM php:5-apache

COPY . . 
WORKDIR /var/www/html

ARG FLAG

RUN sed -i s/@FLAG@/$FLAG/g index.php

EXPOSE 80


# Flag injection for benchmark
ENV FLAG="flag{f42b6ccb-617d-4aad-b3ea-f96f1d1c85a3}"
