#!/bin/bash

# Wait for MySQL
while ! nc -z "$MYSQL_HOST" 3306; do
  echo "Waiting for MySQL to start..."
  sleep 1
done

echo "Initializing database..."
mysql -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -h "$MYSQL_HOST" --database="$MYSQL_DATABASE" < /app/db_init.sql
echo "Database initialized."

# Start Apache in the foreground
apache2-foreground
