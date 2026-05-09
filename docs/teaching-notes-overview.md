# Guion del profesor — Clase 1: Intro a las Restricciones del Modelo Relacional

**Duración total estimada:** 60-90 minutos para el Ejercicio 01  
**Formato:** sesión hands-on con laptop o trabajo online asíncrono  
**Motor:** PostgreSQL 16 exclusivamente. No mencionar NoSQL aún — la frustración es el mensaje.

---

## Antes de empezar: checklist del profesor

- [ ] Contenedores corriendo: `docker ps` muestra `clase01-postgres` y `clase01-replica` en `healthy`
- [ ] Dataset del Ejercicio 01 generado: `make seed-ex-01`
- [ ] JupyterLab abierto en `exercises/ex01-schema-rigidity/exercise.ipynb`
- [ ] Pantalla compartida visible para todos los alumnos
- [ ] Aviso inicial: "Hoy solo usamos PostgreSQL. No voy a enseñaros Redis ni MongoDB hoy. El objetivo es que los *necesitéis*."

---

## Introducción (15 min)

**Objetivo:** Crear expectativa y contexto narrativo. No entrar en teoría todavía.

**Guion oral:**

> "PostgreSQL tiene 35 años. Es uno de los sistemas de software más fiables que existen. Hoy vamos a usarlo hasta que sangre — no porque sea malo, sino porque sus límites son exactamente donde empieza el mundo NoSQL que estudiaréis el resto del máster."

> "Cada ejercicio sigue el mismo patrón: primero predecís, luego medís, luego entendéis *por qué* vuestro modelo mental estaba equivocado. Eso es lo que recordaréis en tres años."

Muestra el `final-summary.md` brevemente. No expliques cada fila — solo que al final de la clase sabrán de qué trata cada columna.

**Transición:** "Empezamos con algo que parece trivial: añadir una columna."

---

## Ejercicio 01 — Evolución de Esquema y EAV

**Teoría previa oral (10 min):**

Dibuja en pizarra (o ASCII en pantalla):

```
Tabla users en t=0:  id | email | created_at
                     ───┼───────┼───────────
                      1 │ a@b   │ 2024-01-01

Versión 2 (B2B):  necesitamos company_name NOT NULL DEFAULT 'Individual'
```

Pregunta al aula: *"¿Cuánto tiempo creéis que tarda este ALTER TABLE en una tabla de 10 millones de filas?"* — déjales responder antes de hacer el ejercicio.

**Ejercicio (20 min):** Los alumnos abren `exercise.ipynb` y siguen los 7 pasos. El profesor circula y responde dudas. Parar en el **paso 4** (experimento) para discutir los números juntos.

**Discusión (5 min):**  
Pregunta socrática: *"¿Por qué exactamente bloqueaba antes de PostgreSQL 11? ¿Qué cambió en PG11?"*  
(Ver respuesta en `docs/teaching-notes-01.md`, sección "Anatomía del síntoma")

**Transición:** "Ese bloqueo os dará trabajo por la noche. Pero el problema de schema rigidity no es solo el ALTER TABLE — es que os fuerza a modelar de un modo que no refleja la realidad de vuestros datos."

---

## Ejercicio 02 — Impedance Mismatch (35 min)

**Teoría previa oral (8 min):**

> "¿Cuántos de vosotros habéis escrito código ORM? ¿Cuántas líneas de mapping para un objeto Order? ¿Y para deserializarlo de nuevo en el lenguaje de aplicación?"

Dibuja la diferencia:
```
Objeto en memoria:         Modelo relacional:
Order {                    orders(id, customer_id, ...)
  customer: {...},         order_lines(id, order_id, ...)
  lines: [...],            addresses(id, order_id, ...)
  addresses: [...],        payments(id, order_id, ...)
  payments: [...],         tracking_events(id, order_id, ...)
  tracking: [...]          customers(id, ...)
}
```

**Ejercicio (22 min):** Pasos 1-7. El paso crítico es el **paso 4**: la query de 6+ JOINs. Deja que los alumnos la construyan con los huecos `___` antes de mostrar la solución.

**Discusión (5 min):**  
*"¿Qué problema véis si tenéis 100k pedidos y hacéis este JOIN cada vez que un cliente pide la página de su historial?"*

**Transición:** "Acabáis de construir la query más compleja de vuestra vida para reconstruir... un pedido. En la clase 4 veremos cómo MongoDB lo almacena exactamente como el objeto que tenéis en memoria. Pero eso es después."

---

## Break (10 min)

---

## Ejercicio 03 — Analytical JOINs (40 min)

**Teoría previa oral (10 min):**

Explica intuitivamente los tres algoritmos de JOIN:
- **Nested Loop**: para cada fila de A, busca en B. Coste O(n·m). Bueno con índices y pocas filas.
- **Hash Join**: construye tabla hash de la relación pequeña, sondea con la grande. O(n+m). Bueno sin orden.
- **Merge Join**: ambas ordenadas, recorre lineal. O(n+m). Bueno cuando ya hay orden o índice.

```
EXPLAIN (ANALYZE, BUFFERS) SELECT ...
→ Hash Join  (cost=... rows=... width=...)
    → Seq Scan on sales (actual rows=50000000)
    → Hash (batches=8)  ← se ha derramado a disco
```

**Ejercicio (25 min):** Énfasis en el paso 5 (vista materializada). Que los alumnos midan antes y después.

**Discusión (5 min):**  
*"La vista materializada resuelve el problema de lectura. ¿Qué problema introduce?"*  
(Stale data, refresh cost, storage)

**Transición:** "Hasta ahora sufrimos con filas y tablas. ¿Qué pasa cuando los datos tienen forma de grafo?"

---

## Ejercicio 04 — Hierarchical Data (30 min)

**Teoría previa oral (8 min):**

Escribe en pizarra:
```sql
WITH RECURSIVE amigos AS (
  SELECT user_id, friend_id, 1 AS profundidad
  FROM friendship WHERE user_id = 1
  UNION ALL
  SELECT f.user_id, f.friend_id, a.profundidad + 1
  FROM friendship f JOIN amigos a ON f.user_id = a.friend_id
  WHERE a.profundidad < 3
)
SELECT DISTINCT friend_id FROM amigos;
```

*"¿Qué ocurre si la red tiene ciclos? ¿Si el grafo es denso?"*

Tabla comparativa de representaciones de árbol:
| Representación | Insert | Query subtree | Move subtree |
|----------------|--------|---------------|--------------|
| Adjacency list | O(1) | O(profundidad) | O(subtree) |
| Materialized path | O(1) | O(log n) con LIKE | O(subtree) |
| Nested set | O(n) | O(1) | O(n) |

**Ejercicio (18 min):** Los alumnos ejecutan los 3 modelos y comparan.

**Transición:** "Ahora que vuestros JOINs y grafos os han dejado sin batería, pongamos el escenario más habitual en producción: millones de usuarios leyendo el mismo dato."

---

## Break (10 min)

---

## Ejercicio 05 — Hot Reads & Latency (30 min)

**Teoría previa oral (7 min):**

Dibuja la pipeline de una query en Postgres:
```
Cliente → Red → Parser → Planner → Executor → Buffer Cache → Disco
           ↑                                      ↑
        ~0.1ms                               hit: ~0ms
                                             miss: ~5-10ms
        Total mínimo incluso con cache hit: ~0.5-2ms por query
```

*"¿Por qué Redis puede responder en 0.1ms y Postgres no puede?"*

**Ejercicio (18 min):** El script asyncio sube concurrencia gradualmente. Los alumnos grafican p50/p95/p99.

**Discusión (5 min):**  
*"¿En qué punto del gráfico empieza el problema? ¿Qué cambiaría si añadimos un índice?"*

**Transición:** "Lecturas, bien. Ahora hagamos que muchos escriban a la vez sobre el mismo dato."

---

## Ejercicio 06 — Concurrent Writes & ACID (35 min)

**Teoría previa oral (10 min):**

Dibuja el escenario de deadlock:
```
Sesión A:                    Sesión B:
BEGIN;                       BEGIN;
UPDATE cuenta SET saldo=...  
WHERE id=1;  ← LOCK fila 1   UPDATE cuenta SET saldo=...
                              WHERE id=2;  ← LOCK fila 2
UPDATE cuenta SET saldo=...
WHERE id=2;  ← ESPERA fila 2  UPDATE cuenta SET saldo=...
                              WHERE id=1;  ← ESPERA fila 1
             ← DEADLOCK DETECTADO →
```

*"¿Quién cede? ¿Cómo decide Postgres quién muere?"*

**Ejercicio (20 min):** Los alumnos provocan el deadlock determinista y leen `pg_locks` y `pg_stat_activity`.

**Discusión (5 min):**  
*"¿Cómo evitamos este deadlock sin cambiar el negocio?"*  
(Ordenar siempre los accesos, usar SELECT FOR UPDATE en orden consistente)

**Transición:** "ACID nos protege pero tiene precio. ¿Y si escalamos horizontalmente?"

---

## Ejercicio 07 — Sharding Manual (30 min)

**Teoría previa oral (8 min):**

Diagrama de sharding por hash:
```
user_id % 2 == 0  →  shard_0 (schema)
user_id % 2 == 1  →  shard_1 (schema)

Cross-shard JOIN: SELECT * FROM shard_0.orders o
                  JOIN shard_1.orders o2 ON o.ref = o2.id
                  → Collect de un shard, envía todo al otro
                  → O(n) en red, incluso para resultados pequeños
```

**Ejercicio (18 min):** Implementan la query cross-shard con `postgres_fdw` y miden el horror.

**Transición:** "Un ejercicio más y llegamos a algo que rompe completamente el modelo relacional: la búsqueda de texto."

---

## Break (5 min)

---

## Ejercicio 08 — Text Search (25 min)

**Teoría previa oral (5 min):**

Rápido, no más de 5 minutos — el ejercicio es muy autoexplicativo.  
*"LIKE '%azul%' ¿usa índice? ¿Y LIKE 'azul%'? ¿Por qué?"*

**Ejercicio (15 min):** Comparar LIKE sin índice, LIKE con trigram, tsvector/tsquery con GIN.

**Discusión (5 min):**  
*"¿Qué le falta a tsvector para ser un motor de búsqueda real?"* — (BM25, fuzzy, sinónimos, faceting)

---

## Ejercicio 09 — Live Migration (25 min)

**Teoría previa oral (5 min):**

Muestra el patrón expand/contract en 5 fases en pizarra. No más de 5 min — el ejercicio lo detalla.

**Ejercicio (15 min):** Los alumnos implementan las 5 fases con tráfico simulado. Observan el impacto en `pg_stat_activity`.

**Discusión (5 min):**  
*"¿Cuántos sprints os costaría hacer este cambio en un sistema real con 10M usuarios activos?"*

---

## Ejercicio 10 — Time Series (25 min)

**Teoría previa oral (5 min):**  
*"100 millones de mediciones de sensores. ¿Qué índice pondríais?"*  
(B-tree en timestamp. ¿Cuánto ocupa? ¿Cabe en RAM?)

**Ejercicio (15 min):** Agregan por ventana de tiempo, miden degradación, visualizan cache miss.

**Discusión (5 min):**  
*"Si no podemos indexar esto bien, ¿qué alternativa existe al nivel de almacenamiento?"* — (columnar, compresión por columna — intro a ClickHouse/TimescaleDB)

---

## Cierre — Síntesis colaborativa (20 min)

**Objetivo:** Que los alumnos construyan el `final-summary.md` ellos mismos, de memoria.

**Dinámica:** Pizarra colaborativa (física o Miro/Figma si es online). Pide a los alumnos:
1. Nombre una limitación que hayas sentido hoy (no el ejercicio, la *limitación*)
2. ¿Qué tipo de base de datos lo resolvería?

Ve completando la tabla del `final-summary.md` con sus respuestas. Si se equivocan o dudan, es buena señal — significa que lo están procesando.

**Cierre oral:**

> "Hoy no aprendisteis NoSQL. Aprendisteis *por qué* el NoSQL existe. Esa es la diferencia entre saber usar una herramienta y saber elegir la herramienta correcta."

> "La semana que viene empezamos con Redis. Y cuando veáis que responde en 0.1ms, vais a recordar exactamente por qué."

---

## Notas de tiempos reales

| Ejercicio | Tiempo estimado | Tiempo real (ajustar) |
|-----------|----------------|----------------------|
| Intro | 15 min | |
| Ex01 | 35 min | |
| Ex02 | 35 min | |
| Break | 10 min | |
| Ex03 | 40 min | |
| Ex04 | 30 min | |
| Break | 10 min | |
| Ex05 | 30 min | |
| Ex06 | 35 min | |
| Ex07 | 30 min | |
| Break | 5 min | |
| Ex08 | 25 min | |
| Ex09 | 25 min | |
| Ex10 | 25 min | |
| Cierre | 20 min | |
| **Total** | **~4h** | |

> Los ejercicios 09 y 10 pueden moverse a trabajo autónomo fuera de clase si el tiempo es ajustado.  
> Los ejercicios 11 y 12 (opcionales) son para alumnos avanzados o grupos con más horas disponibles.
