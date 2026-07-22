# Balance360 — Deploy a producción

Producción corre en la **VM** (Ubuntu 24.04) detrás de **srv-nginx** (.9), que termina el HTTPS y proxea por HTTP al puerto 8000 de la VM. En la VM todo vive en Docker Compose (`docker-compose.prod.yml`): servicio `db` (Postgres 16, sin puerto publicado, datos en el volumen `postgres_data`) y servicio `app` (imagen construida con el `Dockerfile` del repo). El `.env` de producción vive solo en la VM, nunca en git.

> `render.yaml` y `Caddyfile` quedan en el repo como alternativas (Render fue el interino; Caddy no se usa porque nginx ya termina TLS).

---

## 1. Actualizar de desarrollo a producción

### Antes de pushear (en dev)

1. Correr los tests: `uv run pytest`
2. Si cambiaste modelos: generar la migración, **revisarla** y commitearla junto con el código:
   ```
   alembic revision --autogenerate -m "descripcion"
   ```
3. Commit + push a GitHub (rama `fastapi`).

### En la VM

```bash
ssh johnny@<vm>
cd ~/Balance360
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f app   # verificar el arranque
```

Qué hace `up -d --build`:

- Reconstruye la imagen. Si `pyproject.toml`/`uv.lock` no cambiaron, la capa de dependencias sale de cache y el build es rápido.
- Recrea solo el contenedor `app`; el `db` y sus datos (volumen) **no se tocan**.
- Al arrancar, `docker-entrypoint.sh` corre `alembic upgrade head` y recién después levanta uvicorn. Con `set -e`, si una migración falla la app **no arranca** → mirar los logs.

Un redeploy nunca borra datos: la base vive en el volumen, no en el contenedor.

---

## 2. Alembic en producción

**Caso normal: no hacés nada.** Las migraciones se generan en dev, viajan por git y el entrypoint las aplica solo en cada deploy. Nunca corras `alembic revision --autogenerate` en prod.

Para diagnosticar o aplicar a mano:

```bash
docker compose -f docker-compose.prod.yml exec app alembic current    # revisión aplicada
docker compose -f docker-compose.prod.yml exec app alembic history    # todas las revisiones
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

Si la app no bootea (migración rota, crash-loop), `exec` no sirve porque necesita el contenedor corriendo. Usá `run`, que levanta un contenedor temporal solo para el comando:

```bash
docker compose -f docker-compose.prod.yml run --rm app alembic current
docker compose -f docker-compose.prod.yml run --rm app alembic upgrade head
```

Precauciones:

- `downgrade` con mucho cuidado: varias migraciones del proyecto tienen downgrade incompleto o en `None`.
- Antes de una migración destructiva (drop de columna/tabla), hacer backup (sección 4).

---

## 3. Pasar la DB de desarrollo a producción

> **⚠️ Esto pisa TODO lo que haya en prod.** Solo tiene sentido mientras prod no tenga datos propios. El día que prod sea la fuente de verdad, este camino queda prohibido (en todo caso será prod→dev).

### 3.1 Dump en dev (Windows)

El Postgres local corre en docker-compose, y PowerShell corrompe binarios si redirigís con `>`. Por eso el dump se genera **dentro** del contenedor y se saca con `docker cp`:

```powershell
docker exec balance360-db-1 pg_dump -U postgres -d balance360 -Fc -f /tmp/balance360.dump
docker cp balance360-db-1:/tmp/balance360.dump .\balance360.dump
```

### 3.2 Copiar a la VM

```powershell
scp .\balance360.dump johnny@<vm>:~/
```

### 3.3 Restore en prod

Con la app apagada para que nadie escriba durante el restore:

```bash
cd ~/Balance360
docker compose -f docker-compose.prod.yml stop app
docker compose -f docker-compose.prod.yml cp ~/balance360.dump db:/tmp/
docker compose -f docker-compose.prod.yml exec db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges /tmp/balance360.dump'
docker compose -f docker-compose.prod.yml start app
```

- `--clean --if-exists`: borra y recrea los objetos existentes.
- `--no-owner --no-privileges`: el dump se hizo como `postgres` pero en prod el usuario es otro; sin esto llueven errores de ownership.
- El dump incluye la tabla `alembic_version`, así que prod queda en la misma revisión que dev y el próximo deploy sigue derecho.
- **Después de restaurar: cambiar la contraseña de admin** (la de dev estuvo expuesta en el repo público).

---

## 4. Backup de producción

En la VM (bash redirige binarios sin problema, a diferencia de PowerShell):

```bash
docker compose -f docker-compose.prod.yml exec db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backup_$(date +%Y%m%d).dump
```

---

## 5. Referencia: primer arranque en una VM limpia

1. Clonar el repo: `git clone https://github.com/JohnnySalvati/Balance360.git && cd Balance360`
2. Crear `.env` (no versionado) con al menos:

   ```
   POSTGRES_USER=balance360
   POSTGRES_PASSWORD=<secreto>
   POSTGRES_DB=balance360
   DATABASE_URL=postgresql+psycopg://balance360:<secreto>@db:5432/balance360
   SECRET_KEY=<aleatorio largo>
   AFIP_ENV=homo
   ```

   El host de `DATABASE_URL` es `db`: el nombre del servicio en el compose.
3. `docker compose -f docker-compose.prod.yml up -d --build`
4. Restaurar datos (sección 3) o dejar que las migraciones creen el esquema vacío.
