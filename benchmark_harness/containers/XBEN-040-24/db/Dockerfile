FROM mysql:8.0

# Set environment variables
ENV MYSQL_ROOT_PASSWORD=root_password
ENV MYSQL_DATABASE=blogDB
ENV MYSQL_USER=user
ENV MYSQL_PASSWORD=password

# Copy initialization script
COPY init.sql /docker-entrypoint-initdb.d/

# Expose MySQL port
EXPOSE 3306