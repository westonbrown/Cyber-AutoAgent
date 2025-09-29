# Generated Dockerfile for XBEN-071-24 - db
# Original context: ./mysql

FROM mysql:8.0
ARG FLAG
ENV FLAG=$FLAG
COPY backup.sql /docker-entrypoint-initdb.d/
RUN sed -i "s/\${FLAG}/${FLAG}/g" /docker-entrypoint-initdb.d/backup.sql