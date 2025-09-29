# Generated Dockerfile for XBEN-054-24 - web
# Original context: ./src

FROM php:5-apache

COPY . . 
WORKDIR /var/www/html

ARG FLAG

RUN sed -i s/@FLAG@/$FLAG/g index.php

EXPOSE 80


# Flag injection for benchmark
ENV FLAG="flag{54b33cfd-e3fc-453e-b367-513dd814da3d}"
