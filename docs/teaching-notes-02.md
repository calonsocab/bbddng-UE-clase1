# Teaching Notes — Ejercicio 02: Impedance Mismatch

**Ejercicio:** `exercises/ex02-impedance-mismatch/exercise.ipynb`  
**Tiempo de lectura:** 20 minutos  
**Para:** profesor que da la sesion + alumno avanzado que estudia por su cuenta

---

## 1. Concepto de fondo

El impedance mismatch objeto-relacional aparece porque una aplicacion suele trabajar con agregados de dominio y la base relacional trabaja con tablas. Un pedido real no es solo una fila:

```text
Order
  customer
  lines[]
    product
  billingAddress
  shippingAddress
  payment
  shipment
    trackingEvents[]
```

En un diseño normalizado, ese objeto se reparte:

```text
orders
customers
order_lines
products
order_addresses
payments
shipments
tracking_events
```

La normalizacion no es un error. Protege integridad, evita duplicacion y permite actualizar un producto o un cliente en un solo sitio. El precio aparece cuando la aplicacion pide el agregado completo. La base devuelve filas; la aplicacion quiere un arbol.

### Aggregate roots de DDD

En Domain-Driven Design, un aggregate root es la entidad que marca el limite de consistencia de un conjunto de objetos. En este ejercicio, `Order` es el root natural: las lineas, pagos, direcciones y tracking existen en relacion con el pedido.

El modelo relacional no sabe que `Order` es una frontera conceptual. Solo sabe que hay tablas y claves foraneas. Esa diferencia explica por que una operacion de negocio simple, "dame el pedido completo", se convierte en una consulta con muchas uniones.

### N+1

N+1 es el patron donde una lectura que conceptualmente deberia ser "dame estos N agregados con sus hijos" se implementa como una primera query para traer los padres y luego una query adicional por cada padre. Es muy habitual cuando un ORM usa lazy loading:

```text
1 query para cargar N pedidos
N queries adicionales para cargar sus lineas
N queries adicionales para cargar pagos, direcciones, tracking...
```

Ejemplo conceptual:

```python
orders = session.query(Order).limit(100).all()  # 1 query
for order in orders:
    print(order.lines)  # 100 queries si lines es lazy
```

El problema no es solo el numero de filas. Es el numero de viajes cliente-servidor, parseos, planificaciones, adquisiciones de snapshot MVCC y ejecuciones. Una query de 3 ms repetida 200 veces ya no es una query de 3 ms.

La formula mental:

```text
Tiempo total aproximado =
  1 query inicial
  + N * (latencia de red + parse/planning + executor + serializacion)
```

En local, con red casi gratis, el patron ya se nota. En una arquitectura real, con aplicacion y base en hosts distintos, TLS, pool de conexiones, p95/p99 y concurrencia, N+1 puede convertirse en una regresion grave aunque cada query individual use indices.

No confundas N+1 con "JOIN lento". N+1 es peor: muchas veces evita escribir el JOIN, pero lo sustituye por un numero grande de consultas pequeñas. En logs de aplicacion se ve como una cascada de queries parecidas:

```sql
SELECT * FROM order_lines WHERE order_id = 101;
SELECT * FROM order_lines WHERE order_id = 102;
SELECT * FROM order_lines WHERE order_id = 103;
...
```

Mitigaciones tipicas dentro del mundo relacional/ORM:

- `JOIN FETCH` o eager loading cuando sabes que necesitas los hijos.
- Carga por lotes: `WHERE order_id = ANY(:ids)` o `WHERE order_id IN (...)`.
- DataLoader/batching en APIs GraphQL.
- Vistas/materialized views si el patron de lectura es estable.
- Proyecciones especificas para lectura en lugar de cargar entidades completas.

La idea pedagogica no es que los ORMs sean malos. La idea es que el modelo objeto invita a navegar relaciones (`order.lines`) y el modelo relacional cobra por cada acceso fisico si no agrupas bien las lecturas.

---

## 2. Recorrido por el codigo del ejercicio

### Paso 1

Presenta la narrativa de Mercat. La idea a fijar es: el alumno ya entiende de negocio que "pedido" es una cosa, pero en SQL se ha convertido en ocho tablas.

### Paso 2

Las tres predicciones cuantitativas fuerzan a poner un modelo mental antes de medir:

- numero de JOINs necesarios,
- filas devueltas para un unico pedido,
- tiempo esperado para reconstruir un pedido y para cargar muchos pedidos.

No corrijas inmediatamente. Vuelve a estas predicciones al final.

### Paso 3

El alumno explora cardinalidades. Debe completar al menos una query con `___`. Es importante que vea que las tablas hijas (`order_lines`, `tracking_events`) tienen muchas mas filas que la tabla raiz (`orders`).

El punto didactico de elegir un pedido con varias lineas y varios eventos no es buscar un "pedido raro", sino construir un caso minimo donde la multiplicacion sea visible. Si el pedido tiene 4 lineas y 4 eventos, el resultado tabular puede tener 16 filas aunque el negocio siga hablando de "un pedido".

Explicacion oral sugerida:

> "SQL trabaja con relaciones planas. Cuando juntamos dos tablas hijas que representan listas distintas del mismo agregado, aparecen combinaciones. Luego la aplicacion tiene que deshacer esa forma tabular y volver al arbol."

### Paso 4

La query principal reconstruye `Order`. Deben fijarse en dos hechos:

1. La query usa muchas tablas pero, para un `order_id`, PostgreSQL puede resolverla rapido si los indices estan bien.
2. El resultado no es un objeto. Es una tabla multiplicada: cada combinacion de linea y evento produce una fila.

El notebook ya no incluye `EXPLAIN` como celda de alumno porque distraia del objetivo principal. Si un alumno pregunta por que el pedido aislado tarda tan poco, puedes abrir `psql` o añadir temporalmente `EXPLAIN (ANALYZE, BUFFERS)` para mostrar que:

- empieza por `Index Scan` sobre la PK de `orders`,
- usa indices por FK en las tablas hijas,
- usa `Nested Loop` porque la relacion externa tiene una sola fila,
- los buffers suelen estar en cache (`shared hit`),
- `Memoize` puede evitar repetir trabajo para tracking cuando varias filas comparten shipment.

La conclusion correcta es:

> "PostgreSQL esta haciendo lo razonable para este caso puntual. El problema no es que esta query aislada sea lenta; el problema es que hemos tenido que reconstruir un agregado natural con muchas uniones y despues mapear filas repetidas a un objeto."

Para que aparezca dolor de rendimiento, cambia el patron de lectura: muchos pedidos recientes, historial de cliente, endpoint de backoffice, exportacion, o N+1.

### Paso 5 — Comparar el ancho del agregado

El alumno compara dos formas de leer el agregado: primero sin tracking, luego con tracking, despues para una ventana de pedidos recientes. Aqui aparece mejor el coste de lectura porque ya no estamos midiendo una busqueda puntual por PK, sino el patron real de una pantalla de historial o un endpoint de pedidos recientes.

En la maquina de preparacion, con el seed reducido (`60k` pedidos), los tiempos observados fueron:

| Limite de pedidos | Filas tabulares devueltas | Tiempo al traer a pandas | Memoria aproximada en pandas |
|-------------------|---------------------------|---------------------------|------------------------------|
| 100 | 1.311 | 0,23 s | 1,3 MiB |
| 500 | 6.750 | 0,22 s | 6,6 MiB |
| 1.000 | 13.608 | 0,29 s | 13,4 MiB |
| 5.000 | 68.336 | 0,72 s | 67,3 MiB |
| 10.000 | 135.847 | 1,45 s | 133,8 MiB |

Estos numeros son pedagogicamente mejores que "un pedido por id tarda 5 ms", porque muestran dos mecanismos a la vez:

1. La cardinalidad crece por el producto `pedidos x lineas x eventos`.
2. El coste no esta solo en PostgreSQL; tambien esta en red, serializacion, dataframe y mapping a objetos.

### Nota sobre 6M pedidos

No conviene usar 6M pedidos como dataset por defecto. Con las medias actuales, 6M pedidos producirian aproximadamente:

- 18M lineas de pedido,
- 12M direcciones,
- 6M pagos,
- 6M envios,
- 27M eventos de tracking,
- mas de 69M filas totales solo para este ejercicio.

Eso puede ocupar decenas de GB con indices y romper el requisito transversal de que cada ejercicio pueda ejecutarse en menos de 10 minutos en un portatil decente. Si se quiere una demo de profesor con mas dolor, es preferible preparar previamente `make seed-ex-02-full` o crear una variante puntual de benchmark, pero no convertir 6M en el camino normal del alumno.

### Paso 6 — Detectar el patron N+1

La seccion de N+1 hace que el alumno reproduzca de forma controlada el error que suelen esconder los ORMs con lazy loading. El codigo viene dado para que la observacion sea directa. Con solo 100 pedidos recientes, la maquina de preparacion mostro:

```text
N+1: 298 lineas en 257 ms
Una query: 298 lineas en 6 ms
```

Este resultado es mas expresivo que aumentar filas sin mas: con el mismo resultado logico, el patron de acceso cambia el coste en un orden de magnitud.

Subraya que este ratio se obtuvo en local. En cloud, la diferencia normalmente aumenta porque cada query adicional paga latencia de red y competicion por conexiones. Si un alumno obtiene tiempos absolutos mas bajos, que compare ratio y numero de queries, no solo milisegundos.

### Paso 7

El mini-quiz debe evaluar mecanismo, no memoria: por que se trocea el agregado, que coste introduce, y cuando compensa.

---

## 3. Anatomia del sintoma observado

### Planner con 6+ JOINs

PostgreSQL no ejecuta los JOINs necesariamente en el orden escrito. Construye alternativas de plan, estima cardinalidades y elige algoritmos:

- nested loop si una relacion externa es pequena y hay indices en la interna,
- hash join si conviene construir una tabla hash de una relacion,
- merge join si ambas entradas ya llegan ordenadas o el orden compensa.

Con muchas tablas, el espacio de busqueda de ordenes de JOIN crece muy rapido. PostgreSQL usa heuristicas y limites de planificacion para no explorar todo. En este ejercicio, el filtro por `o.id` hace que el plan sea sencillo: se empieza por una fila de `orders` y se encadenan busquedas por indice.

El riesgo aparece cuando la query ya no filtra por un unico pedido:

```sql
WHERE o.placed_at >= now() - interval '30 days'
```

Entonces hay miles de pedidos, varias lineas por pedido y varios eventos por shipment. El resultado puede explotar:

```text
pedidos x lineas medias x eventos medios
```

Esto no es un bug de PostgreSQL. Es consecuencia de pedir una forma de arbol a un motor que devuelve relaciones.

### 3NF vs rendimiento de lectura

La tercera forma normal evita duplicacion. Eso es bueno para escrituras y consistencia:

- el producto vive en `products`,
- el cliente vive en `customers`,
- el pago vive en `payments`,
- el tracking vive en `tracking_events`.

Pero una lectura de detalle necesita unirlo todo. El tradeoff clasico:

| Diseno | Ventaja | Coste |
|--------|---------|-------|
| 3NF estricta | Integridad, menos duplicacion | JOINs y mapping en lectura |
| Tabla wide | Lecturas simples | Duplicacion, updates mas caros |
| Vista materializada | Lectura rapida preparada | Frescura y refresh |
| Documento | Agregado cercano a la app | Duplicacion y decisiones de embedding |

---

## 4. Preguntas socraticas

1. **Si la query de un pedido tarda 3 ms, por que sigue siendo un problema?**  
   Porque el coste no es solo el tiempo puntual. Hay complejidad de mapping, riesgo de N+1, filas multiplicadas y fragilidad cuando cambia el agregado.

2. **Que ganamos al no guardar el pedido entero como JSON en una columna?**  
   Constraints, tipos, claves foraneas, estadisticas, indices relacionales y actualizaciones consistentes de entidades compartidas.

3. **Cuando desnormalizarias?**  
   Cuando el patron de lectura es muy frecuente, estable y critico, y el coste de mantener duplicacion o una vista materializada es menor que reconstruir el agregado en cada lectura.

---

## 5. Errores tipicos del alumno

- **"La solucion es no usar JOINs."** Redirigir: el JOIN no es malo; el punto es entender cuando su coste y complejidad dominan.
- **"MongoDB siempre seria mejor."** Redirigir: un documento embebido tambien duplica y complica actualizaciones si las piezas cambian de forma independiente.
- **"N+1 es solo problema del ORM."** Redirigir: el ORM lo hace facil, pero cualquier codigo que ejecute queries por entidad puede caer en lo mismo.
- **"Si hay indices, no hay problema."** Redirigir: los indices ayudan a encontrar filas; no eliminan multiplicacion de cardinalidad ni coste de red/mapping.

---

## 6. Conexion con el temario

Este dolor justifica la Clase 4: MongoDB. El modelo documental permite almacenar ciertos agregados con una forma parecida a la que consume la aplicacion. No elimina los tradeoffs: cambia JOINs por decisiones de embedding, duplicacion, actualizacion y versionado de documentos.

---

## 7. Lecturas opcionales

- Martin Fowler, *Patterns of Enterprise Application Architecture*, capitulos sobre Data Mapper e Identity Map.
- Eric Evans, *Domain-Driven Design*, capitulos sobre aggregates.
- PostgreSQL documentation: `EXPLAIN` y planner statistics.
- Martin Kleppmann, *Designing Data-Intensive Applications*, capitulos 2 y 3.
