# BBDDNG UE Clase 1 — Evolución de Esquema en PostgreSQL

**Asignatura:** Bases de Datos de Nueva Generación · Máster en Big Data  
**Clase:** 1 de 8 · Introducción  
**Motor:** PostgreSQL 16

Este repositorio contiene el material ejecutable de los primeros ejercicios de la Clase 1. El objetivo es que el alumno experimente por qué el modelo relacional, aun siendo robusto, introduce fricción cuando el esquema cambia o cuando la aplicación necesita reconstruir agregados complejos.

---

## Empieza aquí

Si es la primera vez que abres este repositorio, ejecuta estos comandos desde una terminal:

```bash
git clone https://github.com/calonsocab/bbddng-UE-clase1.git
cd bbddng-UE-clase1

make venv
make up
make seed-ex-01
make exercise-01
```

El último comando abre JupyterLab con el notebook del ejercicio.

[Ver el notebook del Ejercicio 01 en GitHub](exercises/ex01-schema-evolution/exercise.ipynb)

Para continuar con el Ejercicio 02:

```bash
make seed-ex-02
make exercise-02
```

Para continuar con el Ejercicio 03, sobre reporting y preagregacion:

```bash
make seed-ex-03
make exercise-03
```

Para continuar con el Ejercicio 04, sobre hot reads y latencia:

```bash
make seed-ex-04
make exercise-04
```

Para continuar con el Ejercicio 05, sobre escrituras concurrentes:

```bash
make seed-ex-05
make exercise-05
```

Si tienes problemas con Docker, Python o pgAdmin, consulta [Solución de problemas](docs/troubleshooting.md).

Material para el profesor:

- [Guion completo de la clase](docs/teaching-notes-overview.md)
- [Teaching notes del Ejercicio 01](docs/teaching-notes-01.md)
- [Teaching notes del Ejercicio 02](docs/teaching-notes-02.md)
- [Teaching notes del Ejercicio 03](docs/teaching-notes-03.md)
- [Teaching notes del Ejercicio 04](docs/teaching-notes-04.md)
- [Teaching notes del Ejercicio 05](docs/teaching-notes-05.md)

---

## Qué aprenderás

Al completar el ejercicio serás capaz de:

1. Explicar por qué una evolución B2C → B2B implica cambios de esquema, datos antiguos/nuevos, validaciones e informes.
2. Medir el primer `ALTER TABLE` de esa evolución y entender por qué sigue requiriendo locks.
3. Observar el efecto convoy: una transacción activa hace esperar al DDL y el DDL hace esperar a queries normales.
4. Entender por qué aparece EAV como escape hatch ante la rigidez de esquema.
5. Comparar EAV con una tabla relacional por subtipo para informes y filtros multiatributo.
6. Conectar el problema con el patrón de **schema versioning** que se verá en MongoDB.
7. Reconstruir un agregado `Order` normalizado y explicar el coste del mapping objeto-relacional.
8. Medir por que lecturas calientes repetidas degradan p95/p99 aunque una query individual parezca rapida.
9. Observar como locks, waits y deadlocks aparecen al coordinar escrituras concurrentes.

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

## Flujo de trabajo

```text
B2C inicial
   ↓
Mercat necesita vender a empresas
   ↓
Evolución del esquema: columnas, locks, datos antiguos y nuevos
   ↓
Tentación de usar EAV para evitar cambios frecuentes de tabla
   ↓
Coste real de EAV en informes, filtros y validaciones
   ↓
Conexión con schema versioning en MongoDB
```

El ejercicio está diseñado para ejecutarse en orden. No hace falta saber internos de PostgreSQL: el notebook te va guiando por los experimentos.

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
│   ├── ex01_schema_rigidity.py
│   ├── ex02_impedance_mismatch.py
│   ├── ex03_reporting_preaggregation.py
│   ├── ex04_hot_reads_latency.py
│   └── ex05_concurrent_writes.py
├── exercises/
│   ├── ex01-schema-evolution/
│   ├── ex02-impedance-mismatch/
│   ├── ex03-reporting-preaggregation/
│   ├── ex04-hot-reads-latency/
│   └── ex05-concurrent-writes/
│       ├── README.md
│       └── exercise.ipynb
└── docs/
    ├── teaching-notes-overview.md
    ├── teaching-notes-01.md
    ├── teaching-notes-02.md
    ├── teaching-notes-03.md
    ├── teaching-notes-04.md
    ├── setup-previo.md
    ├── proximas-clases.md
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
| 6 | Desafío aplicado sobre los límites de EAV |
| 7 | Cierre, reflexión y quiz externo |

Las preguntas de evaluación y las soluciones las facilitará el profesor por los canales de la asignatura.

---

## Qué debes completar

- Ejecutar el notebook entero, celda a celda.
- Comparar tus tiempos con los resultados orientativos comentados en clase.
- Responder las reflexiones, polls o quizzes que indique el profesor.
- Llegar al cierre con una explicación propia de por qué evolucionar un esquema no es solo hacer `ALTER TABLE`.

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
