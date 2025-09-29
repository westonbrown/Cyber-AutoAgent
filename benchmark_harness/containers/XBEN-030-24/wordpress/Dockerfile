# Generated Dockerfile for XBEN-030-24 - wordpress
# Original context: ./wordpress

FROM wordpress:latest
COPY . /var/www/html
ARG FLAG
ENV FLAG=$FLAG
RUN echo "$FLAG" > /opt/flag.txt
RUN chown -R www-data:www-data /var/www/html