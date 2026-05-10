# Ejercicio 04 — Hot Reads y Latencia

**Tiempo estimado:** 45 minutos  
**Dificultad:** Intermedia  
**Tema de fondo:** lecturas calientes, p50/p95/p99, concurrencia, read models operacionales

---

## Antes de abrir el notebook

Desde la raiz del repositorio:

```bash
make up
make seed-ex-04
make exercise-04
```

En este ejercicio `make seed-ex-04` carga el dataset completo, porque el objetivo es observar latencia y percentiles con suficiente volumen.

---

## Objetivo de aprendizaje

Al terminar este ejercicio el alumno sera capaz de:

1. Distinguir una query rapida aislada de una lectura caliente bajo carga.
2. Medir p50, p95 y p99 en vez de quedarse solo con la media.
3. Explicar por que PostgreSQL paga trabajo repetido aunque los datos esten en buffer cache.
4. Ver como una proyeccion preparada dentro de PostgreSQL reduce latencia de lectura.
5. Entender el coste de mantener datos derivados para lecturas operacionales.

---

## Narrativa de negocio

Mercat muestra una ficha resumida de producto:

```text
precio, stock, rating, views, carts, compras recientes y score de popularidad.
```

Los productos mas populares reciben muchas lecturas repetidas. La query normalizada es correcta, pero recalcula metricas recientes desde eventos cada vez. Cuando muchos usuarios consultan esos productos a la vez, la latencia de cola y el trabajo repetido se vuelven visibles.

---

## Dataset

| Tabla | Rol |
|-------|-----|
| `ex04_products` | Catalogo de productos |
| `ex04_inventory` | Stock y almacenes |
| `ex04_reviews` | Rating agregado |
| `ex04_product_events` | Eventos recientes de vista, carrito y compra |
| `ex04_product_summary` | Proyeccion preparada para lectura caliente |

El dataset usa una distribucion sesgada: pocos productos concentran gran parte de los eventos.

---

## Estructura del ejercicio

| Paso | Descripcion |
|------|-------------|
| 1 | Contexto y objetivo |
| 2 | Setup y exploracion del dataset |
| 3 | Lectura individual normalizada |
| 4 | Lecturas repetidas secuenciales |
| 5 | Concurrencia y percentiles |
| 6 | Proyeccion preparada dentro de PostgreSQL |
| 7 | Cierre y reflexion |

El guion tecnico del profesor esta en [../../docs/teaching-notes-04.md](../../docs/teaching-notes-04.md).
