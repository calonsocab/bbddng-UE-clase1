# Próximas clases — conexión con el temario

Este repositorio contiene actualmente el **Ejercicio 01** completo y ejecutable. Esta página sitúa el ejercicio dentro del resto del máster.

| # | Estado | Limitación relacional | Síntoma que se quiere observar | Clase futura |
|---|--------|-----------------------|-------------------------------|--------------|
| 01 | Implementado | Evolución de esquema y EAV | Cambiar el modelo B2C → B2B requiere DDL, locks, migraciones o escapes como EAV | Clase 4: MongoDB |
| 02 | Roadmap | Impedance mismatch | Reconstruir objetos de dominio requiere múltiples JOINs y mapping ORM | Clase 4: MongoDB |
| 03 | Roadmap | JOINs analíticos | Consultas analíticas con muchas tablas degradan y empujan a desnormalizar | Clases 3/4: Cassandra, MongoDB |
| 04 | Roadmap | Datos jerárquicos/grafo | Recorridos con `WITH RECURSIVE` son difíciles de modelar y optimizar | Clase 6: Neo4J |
| 05 | Roadmap | Lecturas calientes | Hay un suelo de latencia y p99 bajo concurrencia | Clase 2: Redis |
| 06 | Roadmap | Escritura concurrente | Locks, waits y deadlocks bajo contención | Clases 2/3: Redis, Cassandra |
| 07 | Roadmap | Sharding manual | FKs y JOINs cross-shard son inviables o muy costosos | Clase 3: Cassandra |
| 08 | Roadmap | Búsqueda de texto | `LIKE`/`tsvector` no cubren relevancia, fuzzy, faceting y análisis avanzado | Clase 5: Elasticsearch |
| 09 | Roadmap | Migración en caliente | Expand/contract, backfill y dual write para cambiar esquemas vivos | Clase 4: MongoDB |
| 10 | Roadmap | Series temporales | Volumen, índices B-tree y queries de ventana degradan | Clase 7/8: Kafka, TimescaleDB |

## Síntesis del Ejercicio 01

El modelo relacional no falla porque no tenga soluciones. Tiene varias: columnas, constraints, tablas por subtipo, vistas, vistas materializadas y migraciones controladas. El punto es que todas obligan a coordinar la evolución del esquema cuando el negocio cambia.

EAV intenta escapar de esa coordinación guardando atributos como filas. Evita algunos `ALTER TABLE`, pero traslada el coste a consultas, validaciones, índices y mantenibilidad.

La Clase 4 retomará esta tensión con MongoDB y el patrón de **schema versioning**, donde documentos de distintas versiones pueden convivir y la aplicación aprende a interpretarlos.
