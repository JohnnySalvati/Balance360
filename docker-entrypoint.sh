#!/bin/sh
set -e

# Aplica las migraciones pendientes antes de levantar la app.
alembic upgrade head

# 'exec' reemplaza el shell por uvicorn: uvicorn pasa a ser el proceso
# principal del contenedor y recibe SIGTERM directamente, permitiendo
# un apagado ordenado en cada deploy/reinicio. Un solo worker por ahora.
# --proxy-headers + --forwarded-allow-ips: uvicorn confía en los headers
# X-Forwarded-* que le manda nginx, para reconstruir bien esquema/host
# (imprescindible para que request.url_for genere https://balance360...).
exec uvicorn balance360.main:app --host 0.0.0.0 --port "${PORT}" \
    --proxy-headers --forwarded-allow-ips="*"
