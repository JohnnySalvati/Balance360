# syntax=docker/dockerfile:1

# Imagen oficial de uv con Python 3.11 ya incluido.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# UV_COMPILE_BYTECODE: precompila .pyc (arranque un poco más rápido).
# UV_LINK_MODE=copy: copia los paquetes en vez de symlinkear la cache
#   (necesario para que la imagen sea autocontenida y portable).
# PYTHONUNBUFFERED: los logs salen al instante, sin buffering.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- Capa 1: dependencias ---
# Copiamos SOLO los archivos de bloqueo primero. Mientras no cambien,
# Docker reutiliza esta capa cacheada y no reinstala nada en cada build.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# --- Capa 2: el proyecto ---
# Ahora sí copiamos el código y instalamos el paquete balance360.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# El venv creado por uv queda en /app/.venv; lo ponemos en el PATH
# para invocar alembic y uvicorn directamente.
ENV PATH="/app/.venv/bin:$PATH"

# Render inyecta $PORT en runtime; 8000 es el default para correr local.
ENV PORT=8000
EXPOSE 8000

# Arranque delegado a un script (forma JSON = manejo correcto de señales).
# El script corre las migraciones y luego 'exec uvicorn'.
CMD ["sh", "docker-entrypoint.sh"]
