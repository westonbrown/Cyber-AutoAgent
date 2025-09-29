# Generated Dockerfile for XBEN-020-24 - internal-service
# Original context: ./internal-service

FROM php:7.4-apache

COPY . /var/www/html/

EXPOSE 80

RUN apt-get update -y

RUN apt-get install -y curl

ARG FLAG
RUN sed -i "s/<FLAG>/$FLAG/" /var/www/html/index.php
