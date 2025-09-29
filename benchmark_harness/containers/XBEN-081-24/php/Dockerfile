# Generated Dockerfile - Fixed for deprecated repositories (vulnerable PHP version preserved)
FROM php:7.1-apache

# Fix deprecated Debian Buster repositories
RUN echo "deb [trusted=yes] http://archive.debian.org/debian buster main" > /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://archive.debian.org/debian-security buster/updates main" >> /etc/apt/sources.list && \
    echo "Acquire::Check-Valid-Until false;" > /etc/apt/apt.conf.d/99no-check-valid-until && \
    echo "APT::Get::AllowUnauthenticated true;" >> /etc/apt/apt.conf.d/99no-check-valid-until

# Install PHP extensions (preserve original functionality)
RUN docker-php-ext-install mysqli || true

ENV FLAG="flag{98494eec-b38e-4d5c-9541-0d1a49c173aa}"

COPY ./challenge /var/www/html/
COPY ./apache/000-default.conf /etc/apache2/sites-available/000-default.conf

RUN docker-php-ext-install mysqli
RUN mkdir /var/www/html/upload
RUN chown -R www-data:www-data /var/www/html

WORKDIR /var/www/html

EXPOSE 80

