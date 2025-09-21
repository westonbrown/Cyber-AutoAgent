#!/bin/bash

# Wait for MySQL
while ! nc -z "$DB_HOST" 3306; do
  echo "Waiting for MySQL to start..."
  sleep 1
done

# Start Apache in the foreground
apache2-foreground
