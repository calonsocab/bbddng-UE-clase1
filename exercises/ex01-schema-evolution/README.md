# Ejercicio 01 — Evolución de Esquema y el Anti-Patrón EAV

**Tiempo estimado:** 40 minutos  
**Dificultad:** Introductoria  
**Tema de fondo:** evolución de esquema, locks de DDL, efecto convoy, EAV, tablas por subtipo

---

## Antes de abrir el notebook

Desde la raíz del repositorio:

```bash
make up
make seed-ex-01
make exercise-01
```

El comando `make exercise-01` abre este notebook en JupyterLab:

[exercise.ipynb](exercise.ipynb)

---

## Objetivo de aprendizaje

Al terminar este ejercicio el alumno será capaz de:

1. Explicar por qué evolucionar el esquema de una aplicación viva es más que ejecutar un `ALTER TABLE`
2. Medir el coste del primer `ALTER TABLE` de una evolución B2C → B2B
3. Observar el efecto convoy: una transacción activa hace esperar al DDL y el DDL hace esperar a queries normales
4. Identificar por qué aparece EAV como escape hatch ante la rigidez de esquema
5. Comparar EAV con una tabla relacional por subtipo para informes y filtros multiatributo
6. Conectar la evolución parcial de datos con el patrón de schema versioning que se verá en MongoDB

---

## Narrativa de negocio

Trabajas en el equipo de datos de **Mercat**, una plataforma de e-commerce española que empezó como B2C (consumidor final), luego añadió cuentas empresariales (B2B) y ahora también admite freelancers.

El problema real no es "añadir `company_name`". El problema es que el concepto de usuario ha cambiado:

```text
Día 0: Mercat solo necesita usuarios B2C con nombre, email y estado.
Día N: Mercat necesita usuarios B2B con empresa, NIF, sector, empleados y responsable de cuenta.
```

En producción, esa evolución implica DDL, locks, datos antiguos, datos nuevos, backfills, informes, validaciones e índices. Este ejercicio empieza por el cambio mínimo observable (`ALTER TABLE`) y luego muestra por qué algunos equipos intentan evitar migraciones frecuentes con EAV.

---

## Dataset

El script de seed crea dos tablas:

| Tabla | Filas (full / small) | Descripción |
|-------|---------------------|-------------|
| `ex01_users` | 10M / 1M | Usuarios de Mercat (B2C, B2B, Freelancer) |
| `ex01_user_attributes` | ~30M / ~3M | Anti-patrón EAV: atributos como filas clave-valor |

Genera el dataset antes de empezar:
```bash
# Desde la raíz del repositorio
make seed-ex-01         # solo este ejercicio
# o
make seed-fast          # alias general; actualmente genera el ejercicio 01
```

---

## Prerequisitos

- Contenedor `clase01-postgres` corriendo y en estado `healthy` (`make up`)
- Dataset generado (ver arriba)
- JupyterLab instalado (`pip install jupyterlab ipython-sql sqlalchemy psycopg2-binary`)

---

## Estructura del ejercicio (7 pasos)

| Paso | Descripción |
|------|-------------|
| 1 | Contexto y objetivo |
| 2 | ✏️ **Hipótesis previa** — poll externo lanzado por el profesor |
| 3 | Setup y exploración del dataset |
| 4 | Experimento: primer ALTER, efecto convoy y coste de EAV en informes B2B |
| 5 | ✏️ **Modifica y observa** — filtro multiatributo en EAV vs tabla por subtipo |
| 6 | Desafío aplicado — diseña el EAV más doloroso posible |
| 7 | ✏️ **Cierre + quiz externo** para la Clase 4 (MongoDB) |

Las preguntas de poll/quiz y las soluciones las facilitará el profesor por los canales de la asignatura.

El guion técnico del profesor está en [../../docs/teaching-notes-01.md](../../docs/teaching-notes-01.md).

---

## Pista para próximas clases

> Este ejercicio demuestra que el modelo relacional te fuerza a **negociar con el esquema** cada vez que el negocio cambia.  
> En la **Clase 4 (MongoDB)** veremos el patrón de **schema versioning**: documentos de distintas versiones conviven y la aplicación aprende a interpretarlos. No elimina la complejidad, pero cambia dónde vive.
