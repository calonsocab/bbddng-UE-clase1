# Preparación previa a la Clase 1

> **Tarea para la noche anterior a la clase.**  
> Tiempo estimado: 20 minutos de trabajo real + 30-40 minutos de espera (generación de datos).  
> Sigue estos pasos en orden. Si algo falla, consulta `docs/troubleshooting.md`.

---

## 1. Prerrequisitos de software

### Docker Desktop
Descarga e instala desde [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)

Verifica que funciona:
```bash
docker --version        # debe mostrar >= 24.x
docker compose version  # debe mostrar >= v2.x
```

**Asigna al menos 4 GB de RAM a Docker** (Preferences → Resources → Memory).  
Para los ejercicios con datasets grandes (ex03, ex07, ex10) se recomiendan 6 GB.

### Python 3.11+
```bash
python3 --version   # debe mostrar 3.11 o superior
```

Si no lo tienes: [https://www.python.org/downloads/](https://www.python.org/downloads/)

### Dependencias Python
```bash
# Desde la raíz del repositorio bbddng-UE-clase1/
pip install -r data-generation/requirements.txt
```

Esto instala: `faker`, `numpy`, `psycopg2-binary`, `asyncpg`, `matplotlib`, `pandas`, `jupyterlab`, `ipython-sql`, `sqlalchemy`, `seaborn`.

---

## 2. Descarga la imagen de Docker (evita esperar en clase)

```bash
docker pull postgres:16
```

Esto descarga ~150 MB. Hazlo con buena conexión antes de clase.

---

## 3. Levanta la infraestructura

```bash
cd bbddng-UE-clase1/
make up
```

Deberías ver algo así en ~30-60 segundos:
```
[+] Levantando PostgreSQL 16 (primaria + réplica)...
[+] Esperando healthchecks...
........... primaria OK
.......... réplica OK
```

Verifica que los contenedores están corriendo:
```bash
docker ps
```
Debes ver `clase01-postgres` y `clase01-replica` con estado `healthy`.

---

## 4. Genera el dataset

> El modo reducido del Ejercicio 01 tarda normalmente 1-3 minutos en un portátil reciente. El modo completo puede tardar bastante más.

```bash
make seed-ex-01
```

Si quieres el dataset completo:

```bash
make seed-ex-01-full
```

**Espacio en disco requerido:**

| Modo | Espacio aproximado |
|------|--------------------|
| `seed-ex-01` | ~1 GB |
| `seed-ex-01-full` | varios GB |

---

## 5. Verifica que todo funciona

Abre el primer ejercicio:
```bash
make exercise-01
```

Se abrirá JupyterLab en tu navegador con el notebook del ejercicio 1. Si ves el notebook cargado y puedes ejecutar la primera celda sin errores, estás listo.

Prueba también la conexión a la base de datos desde la terminal:
```bash
make psql
```
Debes ver el prompt: `clase01=#`

---

## 6. Comprobación rápida de la réplica

```bash
make replica-psql
```
Ejecuta esta query para confirmar que la réplica está siguiendo a la primaria:
```sql
SELECT now(), pg_is_in_recovery(), pg_last_wal_receive_lsn();
```
Debe devolver `pg_is_in_recovery = t`.

---

## Resumen de comandos

```bash
make up           # arranca todo
make seed-fast    # genera datos (rápido)
make exercise-01  # abre el notebook del ejercicio 1
make psql         # acceso a la primaria
make replica-psql # acceso a la réplica
make down         # para los contenedores (los datos persisten)
make clean        # para Y borra todos los datos
```

---

## Si algo falla

Consulta `docs/troubleshooting.md` para los problemas más comunes: memoria de Docker insuficiente, puertos ocupados, datasets pesados, problemas en Mac M1/M2/M3 (ARM).

Si aun así no puedes arrancar, avísame antes de la clase para buscar una solución.
