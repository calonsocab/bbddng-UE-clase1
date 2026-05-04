# clase01-intro — Evolución de Esquema en PostgreSQL

**Asignatura:** Bases de Datos de Nueva Generación · Máster en Big Data  
**Clase:** 1 de 8 · Introducción  
**Motor:** PostgreSQL 16

Este repositorio contiene el material ejecutable del **Ejercicio 01** de la Clase 1. El objetivo es que el alumno experimente por qué evolucionar el esquema de una aplicación viva no es simplemente ejecutar un `ALTER TABLE`.

---

## Qué aprenderás

Al completar el ejercicio serás capaz de:

1. Explicar por qué una evolución B2C → B2B implica cambios de esquema, datos antiguos/nuevos, validaciones e informes.
2. Medir el primer `ALTER TABLE` de esa evolución y entender por qué sigue requiriendo locks.
3. Observar el efecto convoy: una transacción activa hace esperar al DDL y el DDL hace esperar a queries normales.
4. Entender por qué aparece EAV como escape hatch ante la rigidez de esquema.
5. Comparar EAV con una tabla relacional por subtipo para informes y filtros multiatributo.
6. Conectar el problema con el patrón de **schema versioning** que se verá en MongoDB.

---

## Prerrequisitos

| Requisito | Versión recomendada |
|-----------|---------------------|
| Docker Desktop | 24.x o superior |
| Docker Compose | v2 |
| Python | 3.11+ |
| Git | cualquier versión reciente |

No necesitas instalar PostgreSQL localmente: se levanta con Docker.

---

## Arranque desde cero

```bash
# 1. Clona el repositorio
git clone <URL_DEL_REPO>
cd clase01-intro

# 2. Crea el entorno Python
make venv

# 3. Levanta PostgreSQL primaria + réplica
make up

# 4. Genera el dataset reducido del ejercicio 01
make seed-ex-01

# 5. Abre el notebook
make exercise-01
```

El notebook se abrirá en JupyterLab. Sigue las celdas en orden.

---

## Acceso a PostgreSQL

### Terminal `psql`

```bash
make psql
```

Comandos útiles dentro de `psql`:

```sql
\dt
\d ex01_users
\d ex01_user_attributes
\q
```

### pgAdmin

```bash
make up-admin
```

Abre:

```text
http://localhost:8080
```

Login:

```text
Email: admin@clase01.com
Password: admin
```

Para registrar el servidor en pgAdmin:

```text
Host: postgres
Port: 5432
Database: clase01
Username: postgres
Password: postgres
```

---

## Material incluido

```text
.
├── docker-compose.yml
├── Makefile
├── .env.example
├── data-generation/
│   ├── generate_all.py
│   └── ex01_schema_rigidity.py
├── exercises/
│   └── ex01-schema-rigidity/
│       ├── README.md
│       └── exercise.ipynb
└── docs/
    ├── setup-previo.md
    └── troubleshooting.md
```

---

## Flujo del ejercicio 01

| Paso | Contenido |
|------|-----------|
| 1 | Contexto: Mercat evoluciona de B2C a B2B |
| 2 | Poll externo de hipótesis lanzado por el profesor |
| 3 | Setup y exploración del dataset |
| 4 | Primer `ALTER TABLE`, efecto convoy y coste de EAV |
| 5 | Filtro multiatributo en EAV vs tabla por subtipo |
| 6 | Reto opcional para romper EAV |
| 7 | Cierre, reflexión y quiz externo |

Las preguntas de evaluación y las soluciones las facilitará el profesor por los canales de la asignatura.

---

## Comandos útiles

```bash
make help            # lista comandos disponibles
make up              # levanta postgres + réplica
make up-admin        # levanta también pgAdmin
make down            # para contenedores
make clean           # borra contenedores y volúmenes
make seed-ex-01      # genera dataset reducido del ejercicio 01
make seed-ex-01-full # genera dataset completo del ejercicio 01
make exercise-01     # abre JupyterLab con el notebook
make psql            # abre psql en la primaria
```

---

## Solución de problemas

Consulta:

```text
docs/troubleshooting.md
```

Problemas habituales:

- puerto `5432` ocupado,
- Docker sin memoria suficiente,
- dataset no generado,
- pgAdmin sin servidor registrado,
- dependencias Python no instaladas.

---

## Nota

Este repositorio está preparado para que un alumno lo ejecute desde cero en local. Los datasets no se suben a GitHub; se generan con `make seed-ex-01`.

Material didáctico para uso académico. Universidad Europea · Máster en Big Data 2026-2027.
