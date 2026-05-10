# Teaching Notes — Ejercicio 04: Hot Reads y Latencia

**Ejercicio:** `exercises/ex04-hot-reads-latency/exercise.ipynb`  
**Duracion sugerida:** 45 minutos  
**Dataset del ejercicio:** `make seed-ex-04` carga el modo full

## 1. Proposito

El ejercicio muestra una tension distinta a reporting. En reporting, el problema es recalcular una agregacion grande para un cuadro de control. En hot reads, el problema es repetir muchas veces una lectura operacional que parece razonable cuando se ejecuta una sola vez.

La pregunta docente:

> Si una query tarda pocos milisegundos, por que puede seguir siendo un problema en produccion?

Respuesta esperada: porque bajo concurrencia se paga muchas veces el mismo trabajo: adquirir conexion, enviar SQL, parsear/planificar o reutilizar plan, abrir snapshot MVCC, ejecutar joins/agregaciones, leer buffers, serializar respuesta y devolverla por red. Aunque los datos esten en cache de PostgreSQL, ese camino no es gratis.

## 2. Caso de negocio

Mercat tiene una ficha resumida de producto consultada constantemente:

- precio y metadatos de producto;
- stock disponible;
- rating agregado;
- views, carritos y compras de los ultimos 7 dias;
- score de popularidad.

La query normalizada es correcta: une producto, inventario, reviews y agrega eventos recientes. El problema aparece cuando los productos populares reciben muchas lecturas repetidas.

## 3. Dataset

Tablas:

- `ex04_products`: 60k productos.
- `ex04_inventory`: una fila por producto.
- `ex04_reviews`: una fila por producto.
- `ex04_product_events`: eventos con distribucion sesgada por popularidad.
- `ex04_product_summary`: proyeccion preparada con el resumen por producto.

Modo small:

- 300k eventos.
- Util para validar rapido.

Modo full:

- 2M eventos.
- Recomendado para clase porque permite ver latencia y percentiles con mas claridad.

## 4. Paso 3 — Lectura individual

El alumno ejecuta una query normalizada para el producto mas popular. Debe ver que la lectura aislada no parece escandalosa.

Interpretacion:

- PostgreSQL usa indices y buffer cache.
- La query devuelve un resultado correcto.
- El problema todavia no es evidente porque solo hay una peticion.

Mensaje docente: una query individual no describe el comportamiento de un endpoint caliente.

## 5. Paso 4 — Lecturas repetidas secuenciales

El notebook ejecuta la misma lectura muchas veces y calcula p50, p95, p99 y tiempo total.

Interpretacion:

- El usuario individual no espera el total acumulado.
- El sistema si paga todas las ejecuciones.
- La media puede ocultar picos.
- Si 1,000 lecturas repiten la misma respuesta, PostgreSQL esta haciendo trabajo redundante.

Este punto debe enlazar con arquitectura: un backend que consulta PostgreSQL para cada request puede funcionar al principio, pero escala mal si muchos usuarios piden el mismo dato caliente.

## 6. Paso 5 — Concurrencia

El notebook usa `asyncpg` y un pool de conexiones. La latencia medida incluye espera para conseguir conexion, ejecucion SQL y fetch del resultado.

Metricas:

- p50: usuario tipico.
- p95: cola lenta que ya afecta experiencia.
- p99: cola extrema, importante para SLOs.
- throughput: requests por segundo.

Interpretacion esperada:

- p50 puede mantenerse razonable.
- p95/p99 crecen cuando aumenta la concurrencia.
- El limite puede venir de CPU, pool, executor, agregacion de eventos o competencia por recursos compartidos.

No vender un numero concreto. El valor esta en la forma de la curva.

## 7. Paso 6 — Proyeccion preparada

`ex04_product_summary` representa un read model operacional dentro de PostgreSQL. No es una herramienta BI. Es una tabla derivada que guarda la respuesta preparada para una lectura caliente.

Interpretacion:

- La lectura pasa de joins/agregacion a lookup por primary key.
- Baja la latencia y reduce variabilidad.
- El coste no desaparece: se mueve al refresco/mantenimiento de la proyeccion.

Discusion:

- Si stock cambia cada segundo, que parte puede estar derivada?
- Que TTL o frecuencia de refresco seria aceptable?
- Que dato debe ser siempre consistente y que dato admite segundos de desfase?

## 8. Complejidad de PostgreSQL en este escenario

PostgreSQL puede resolver la query. La complejidad aparece por usarlo como sistema que recalcula una lectura caliente para cada request:

- cada request consume conexion o espera en pool;
- cada request abre snapshot MVCC;
- cada request ejecuta agregacion sobre eventos recientes;
- cada request compite por CPU y memoria compartida;
- p95/p99 importan mas que el caso feliz;
- optimizar lectura suele introducir datos derivados y mantenimiento.

Frase de cierre:

> PostgreSQL responde correctamente, pero una lectura correcta no siempre es una lectura operacionalmente barata cuando se repite bajo concurrencia.
