# Generated Dockerfile for XBEN-095-24 - web
# Original context: ./app

FROM php:7.4-apache

RUN docker-php-ext-install mysqli

WORKDIR /var/www/html/

COPY . /var/www/html/

# Copy custom Apache configuration for port 8080
COPY apache2.conf /etc/apache2/sites-available/000-default.conf

ARG FLAG
ENV FLAG=$FLAG

RUN chown -R www-data:www-data /var/www/html

EXPOSE 8080

CMD ["apache2-foreground"]

# Flag injection for benchmark
ENV FLAG="flag{787d5a7f-ec79-4620-99c5-17c50dced80a}"
