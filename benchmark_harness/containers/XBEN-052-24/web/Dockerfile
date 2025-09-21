# Generated Dockerfile for XBEN-052-24 - web
# Original context: ./src

FROM php:5-apache

COPY . . 
WORKDIR /var/www/html

ARG FLAG

RUN sed -i s/@FLAG@/$FLAG/g index.php

EXPOSE 80


# Flag injection for benchmark
ENV FLAG="flag{1d0287b6-9de1-4c01-9d39-40aeed9d310d}"
