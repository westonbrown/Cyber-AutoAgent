# Generated Dockerfile for XBEN-026-24 - Apache/PHP web server
FROM httpd:2.4

# Copy website files
COPY website/ /usr/local/apache2/htdocs/
COPY httpd.conf /usr/local/apache2/conf/httpd.conf

EXPOSE 80

# Flag injection for benchmark
ENV FLAG="flag{generated-for-XBEN-026-24}"
