#!/bin/bash
set -e

echo "=== Spartan PC - Iniciando Contenedor ==="

# Si se usa MySQL, esperar a que el puerto esté disponible
if [ "$DB_ENGINE" = "mysql" ]; then
    echo "Esperando a que la base de datos MySQL ($DB_HOST:$DB_PORT) esté lista..."
    while ! nc -z "$DB_HOST" "$DB_PORT"; do
      sleep 1
    done
    echo "✓ Conexión establecida con MySQL."
fi

# Aplicar migraciones pendientes
echo "Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

# Ejecutar el comando principal (ej. runserver o gunicorn)
exec "$@"
