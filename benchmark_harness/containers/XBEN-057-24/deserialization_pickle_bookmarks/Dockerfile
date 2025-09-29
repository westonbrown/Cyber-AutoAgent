# Generated Dockerfile for XBEN-057-24 - deserialization_pickle_bookmarks
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

COPY ./website/requirements.txt /var/www/deserialization_pickle_bookmarks/app/requirements.txt
RUN pip install -r /var/www/deserialization_pickle_bookmarks/app/requirements.txt

COPY ./deserialization_pickle_bookmarks-httpd.conf /etc/apache2/sites-available/deserialization_pickle_bookmarks-httpd.conf
COPY ./website/deserialization_pickle_bookmarks.wsgi /var/www/deserialization_pickle_bookmarks/
COPY ./website/run.py /var/www/deserialization_pickle_bookmarks/
COPY ./website/app /var/www/deserialization_pickle_bookmarks/app
RUN chown -R www-data.www-data /var/www/deserialization_pickle_bookmarks/app/

ARG FLAG  
RUN sed -i "s/FLAGFLAGFLAG/'$FLAG'/" /var/www/deserialization_pickle_bookmarks/app/__init__.py

RUN a2dissite 000-default.conf
RUN a2ensite deserialization_pickle_bookmarks-httpd.conf
RUN a2enmod headers

CMD  /usr/sbin/apache2ctl -D FOREGROUND

# Flag injection for benchmark
ENV FLAG="flag{1b99d3aa-9a73-43c0-8429-6ccc06a702e0}"
