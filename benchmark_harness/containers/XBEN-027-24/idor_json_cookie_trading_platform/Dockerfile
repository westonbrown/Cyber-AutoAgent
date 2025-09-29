# Generated Dockerfile for XBEN-027-24 - idor_json_cookie_trading_platform
# Original context: ./app

FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y apache2 \
    libapache2-mod-wsgi-py3 \
    python3 \
    python3-pip \
    curl \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

COPY ./website/requirements.txt /var/www/idor_json_cookie_trading_platform/app/requirements.txt
RUN pip install -r /var/www/idor_json_cookie_trading_platform/app/requirements.txt

COPY ./idor_json_cookie_trading_platform-httpd.conf /etc/apache2/sites-available/idor_json_cookie_trading_platform-httpd.conf
COPY ./website/idor_json_cookie_trading_platform.wsgi /var/www/idor_json_cookie_trading_platform/
COPY ./website/run.py /var/www/idor_json_cookie_trading_platform/
COPY ./website/app /var/www/idor_json_cookie_trading_platform/app

ARG FLAG  
RUN echo -n $FLAG > /flag

RUN a2dissite 000-default.conf
RUN a2ensite idor_json_cookie_trading_platform-httpd.conf
RUN a2enmod headers

CMD  /usr/sbin/apache2ctl -D FOREGROUND

# Flag injection for benchmark
ENV FLAG="flag{795a8930-4d69-4e12-9bf0-d6dad2f990d6}"
