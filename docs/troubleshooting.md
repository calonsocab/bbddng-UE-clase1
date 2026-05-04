# Troubleshooting — BBDDNG UE Clase 1

Problemas frecuentes y sus soluciones.

---

## Docker

### La réplica no arranca o se queda en "starting"

**Síntoma:** `docker ps` muestra `clase01-replica` en `starting` o `unhealthy` aunque la primaria esté `healthy`.

**Causa:** La réplica ejecuta `pg_basebackup` al iniciar. Si la primaria no ha terminado de arrancar o el usuario `replicator` aún no existe (se crea en el script de init), `pg_basebackup` falla.

**Solución:**
```bash
docker logs clase01-replica
# Si ves "FATAL: role replicator does not exist"
docker compose down -v
make up
```
Si el problema persiste, arranca solo la primaria primero y espera 30 segundos:
```bash
docker compose up -d postgres
sleep 30
docker compose up -d postgres-replica
```

---

### Puerto 5432 ya está en uso

**Síntoma:** `Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use`

**Causa:** Tienes un PostgreSQL local corriendo en tu máquina.

**Solución (opción A):** Para tu Postgres local temporalmente:
```bash
# macOS con Homebrew
brew services stop postgresql@16

# Linux systemd
sudo systemctl stop postgresql
```

**Solución (opción B):** Cambia el puerto en `.env`:
```bash
# .env
POSTGRES_PORT=5434
REPLICA_PORT=5435
```
Y actualiza la URL de conexión en los notebooks a `localhost:5434`.

---

### Docker se queda sin memoria durante el seed

**Síntoma:** El contenedor de Postgres se reinicia solo, o el seed falla con `OOMKilled`.

**Causa:** Docker Desktop tiene menos de 4 GB asignados.

**Solución:**
1. Abre Docker Desktop → Settings → Resources → Memory
2. Aumenta a 6 GB mínimo (8 GB para ex10 con 100M filas)
3. Aplica y reinicia Docker

---

### Mac M1 / M2 / M3 (Apple Silicon / ARM)

**Síntoma:** `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)`

**Causa:** La imagen `postgres:16` tiene variante ARM nativa. El warning es inofensivo, pero si algo falla:

**Solución:** Fuerza la imagen ARM explícitamente en `docker-compose.yml`:
```yaml
image: postgres:16
platform: linux/arm64
```

Si `psycopg2-binary` falla en la instalación en Mac ARM:
```bash
pip install psycopg2-binary --no-binary psycopg2-binary
# o instala libpq primero:
brew install libpq
pip install psycopg2
```

---

## Datasets y seed

### El seed tarda mucho (más de 1 hora)

**Causa probable:** SSD lento, poca RAM disponible para `work_mem`, o antivirus escaneando los archivos.

**Solución:** Usa el modo reducido para la clase, y genera el completo solo si lo necesitas:
```bash
make seed-ex-01
```

Para el seed completo con más paralelismo (si tienes muchos cores):
```bash
# Edita data-generation/generate_all.py y aumenta WORKERS = 4
```

---

### Error "too many connections" durante el seed

**Síntoma:** `psycopg2.OperationalError: FATAL: sorry, too many clients already`

**Causa:** Los scripts de seed abren múltiples conexiones simultáneas y superan `max_connections = 200`.

**Solución:** Regenera solo el ejercicio disponible:
```bash
make seed-ex-01
```

---

### El volumen de Docker está lleno

**Síntoma:** El seed falla a mitad, logs de Postgres muestran `No space left on device`.

**Solución:**
```bash
# Ver uso de disco de Docker
docker system df

# Limpiar imágenes y contenedores no usados (NO borra volúmenes de clase)
docker system prune

# Si necesitas empezar de cero (BORRA TODOS LOS DATOS):
make clean
```

---

## JupyterLab y notebooks

### "No module named 'psycopg2'" en el notebook

**Causa:** Las dependencias se instalaron en un entorno Python distinto al kernel de Jupyter.

**Solución:**
```bash
# Instala siempre con el mismo Python que usa Jupyter
python3 -m pip install -r data-generation/requirements.txt

# Verifica qué Python usa Jupyter
jupyter kernelspec list
```

Si usas `conda` o `venv`, activa el entorno antes de instalar y de lanzar Jupyter:
```bash
source mi-entorno/bin/activate
pip install -r data-generation/requirements.txt
jupyter lab
```

---

### El magic `%sql` no funciona ("UsageError: Line magic function `%sql` not found")

**Causa:** `ipython-sql` no está instalado o no está cargado.

**Solución:** En la celda del notebook:
```python
%pip install ipython-sql sqlalchemy psycopg2-binary
%load_ext sql
```

---

### La conexión %sql falla ("connection refused")

**Causa:** El contenedor de Postgres no está corriendo o usa un puerto distinto.

**Solución:**
```bash
docker ps   # verifica que clase01-postgres está healthy
```

En el notebook, ajusta el puerto si lo cambiaste en `.env`:
```python
%sql postgresql://postgres:postgres@localhost:5434/clase01
```

---

## Windows

### `make` no reconocido

**Causa:** Windows no incluye `make` por defecto.

**Solución (opción A):** Instala [GNU Make para Windows](https://gnuwin32.sourceforge.net/packages/make.htm) o usa `choco install make`.

**Solución (opción B):** Ejecuta los comandos directamente:
```powershell
# En lugar de "make up"
docker compose up -d postgres postgres-replica
# En lugar de "make psql"
docker exec -it clase01-postgres psql -U postgres -d clase01
```

### Rutas con espacios en PowerShell

Si clonas en una ruta con espacios, los scripts de Python pueden fallar. Recomendamos clonar en `C:\bbddng-UE-clase1\` directamente.

---

## Contacto

Si ninguna solución funciona, abre un issue en el repositorio con:
1. Sistema operativo y versión
2. Versión de Docker (`docker --version`)
3. Output completo del error (`docker logs clase01-postgres 2>&1 | tail -50`)
