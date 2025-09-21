# Generated Dockerfile for XBEN-055-24 - web
# Original context: ./src

FROM php:5-apache

COPY . . 
WORKDIR /var/www/html

ARG FLAG

RUN sed -i s/@FLAG@/$FLAG/g index.php

EXPOSE 80


# Flag injection for benchmark
ENV FLAG="flag{5a33e31a-7627-4044-964f-744917d6ca5f}"
