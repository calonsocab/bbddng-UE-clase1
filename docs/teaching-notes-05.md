# Teaching Notes — Ejercicio 05: Escrituras Concurrentes, Locks y ACID

**Ejercicio:** `exercises/ex05-concurrent-writes/exercise.ipynb`  
**Duracion sugerida:** 45 minutos  
**Dataset:** `make seed-ex-05`

## 1. Proposito

El ejercicio muestra que ACID no es gratis. PostgreSQL protege la consistencia del inventario, pero para hacerlo coordina transacciones mediante locks. Cuando muchos usuarios escriben sobre el mismo producto, una fila de inventario se convierte en punto de serializacion.

La idea central:

> PostgreSQL evita vender stock inexistente, pero esa garantia aparece como waits, cola, deadlocks potenciales y retries de aplicacion.

## 2. Caso de negocio

Mercat lanza una promocion flash con stock limitado para `EX05-SKU-FLASH-001`.

En secuencial, la logica parece trivial:

1. Leer stock.
2. Comprobar que hay unidades.
3. Restar stock.
4. Crear pedido.

Con concurrencia, varias transacciones intentan modificar la misma fila de `ex05_inventory`. PostgreSQL no puede aplicar todas esas escrituras a la vez sin coordinar el orden.

## 3. Paso 3 — Compra secuencial

### Que se pretende hacer

El paso 3 construye la funcion base de compra: `purchase_one`. Es deliberadamente correcta desde el punto de vista transaccional para que el problema no sea "el codigo esta mal", sino "el codigo correcto tambien puede sufrir cuando hay contencion".

La funcion representa una compra de una unidad del producto flash:

1. Abre una conexion desde el pool.
2. Abre una transaccion.
3. Lee y bloquea la fila de inventario con `SELECT ... FOR UPDATE`.
4. Simula algo de trabajo dentro de la transaccion con `pg_sleep`.
5. Si hay stock, crea pedido, crea linea de pedido y descuenta inventario.
6. Si no hay stock, devuelve `sold_out`.
7. Registra el intento en `ex05_order_attempts`.

### Lectura del codigo

```python
async with pool.acquire() as conn:
    async with conn.transaction():
```

El pool gestiona conexiones reutilizables. La transaccion agrupa lectura, decision y escritura. Si algo falla dentro del bloque, PostgreSQL revierte los cambios de esa transaccion.

```sql
SELECT units_available
FROM ex05_inventory
WHERE product_id = $1
FOR UPDATE
```

Esta consulta no solo lee stock. Tambien bloquea la fila de `ex05_inventory` para ese producto hasta `COMMIT` o `ROLLBACK`. Otra transaccion que quiera bloquear o actualizar esa misma fila tendra que esperar.

```python
await conn.execute("SELECT pg_sleep($1::double precision)", lock_delay)
```

Este `sleep` no representa una buena practica. Es una forma controlada de hacer visible el coste de mantener una transaccion abierta: validaciones, llamadas internas, reglas de negocio, calculo de precio o cualquier trabajo que ocurra entre leer stock y confirmar la compra.

```python
if stock and stock > 0:
```

La decision de negocio se toma mientras la fila esta bloqueada. Esto evita que otra transaccion cambie el stock entre la lectura y el descuento.

```sql
UPDATE ex05_inventory
SET units_available = units_available - 1, updated_at = now()
WHERE product_id = $1
```

El descuento ocurre dentro de la misma transaccion. Si el pedido o la linea de pedido fallasen, el descuento tambien se revertiria.

```python
INSERT INTO ex05_order_attempts(...)
```

El intento se registra fuera de la transaccion principal de compra. Esto permite observar latencias, exitos, agotados y errores aunque la operacion de negocio haya terminado con error.

### Resultado esperado

Despues de una compra con stock inicial 30:

- `units_available` baja a 29.
- Se crea un pedido.
- Se registra un intento con `result = 'success'`.

### Interpretacion docente

Este paso debe parecer simple. Esa es la preparacion para el contraste: con un unico comprador, ACID no se percibe como coste. La transaccion dura poco, no hay otra sesion esperando y el resultado es correcto.

La idea que conviene subrayar al alumno es que el problema no aparece porque falte una transaccion. Aparece cuando muchas transacciones correctas compiten por el mismo recurso fisico: una fila de inventario.

## 4. Paso 4 — Compras concurrentes sobre el mismo producto

### Que se pretende hacer

El paso 4 ejecuta 60 compras concurrentes contra el mismo producto flash con 30 unidades disponibles. El objetivo es observar dos cosas al mismo tiempo:

- Consistencia: no se venden mas unidades que las disponibles.
- Coste: varias transacciones tienen que esperar turno para bloquear y modificar la misma fila.

### Lectura del codigo

```python
async def run_purchase_burst(total_customers=60, stock=30, concurrency=20, lock_delay=0.03):
```

La funcion define una rafaga de compras. `total_customers` es el numero total de intentos. `stock` es el inventario inicial. `concurrency` limita cuantas compras pueden estar activas a la vez. `lock_delay` alarga la seccion critica para que la cola sea visible en el aula.

En producción, lock_delay puede aparecer sin pg_sleep por motivos reales:

  - validaciones de negocio dentro de la transacción,
  - triggers,
  - escritura en varias tablas,
  - índices que actualizar,
  - alta concurrencia,
  - CPU saturada,
  - I/O,
  - red,
  - transacciones largas por diseño accidental.

  En local, con 60 compras y PostgreSQL en la misma máquina, todo puede ir tan rápido que el alumno concluya erróneamente:
  “esto no duele”. El lock_delay fuerza una sección crítica más larga para enseñar el mecanismo.

```python
reset_demo(stock=stock)
```

Deja el escenario en estado conocido antes de medir. Esto es importante porque el notebook se puede ejecutar varias veces y las compras modifican datos.

```python
pool = await asyncpg.create_pool(ASYNC_DSN, min_size=1, max_size=concurrency)
sem = asyncio.Semaphore(concurrency)
```

El pool permite varias conexiones a PostgreSQL. El semaforo controla la presion de concurrencia desde Python. Sin semaforo, se lanzarian todas las tareas a la vez y el resultado dependeria mas del cliente que del escenario que se quiere explicar.

```python
results = await asyncio.gather(...)
```

`asyncio.gather` dispara muchas compras y espera a que todas terminen. Cada compra llama a `purchase_one`, por tanto todas intentan ejecutar `SELECT ... FOR UPDATE` sobre el mismo `product_id`.

```python
summary = summarize_latencies(...)
```

El resumen convierte las latencias individuales en metricas docentes: media, p50, p95, p99 y maximo. Para este ejercicio interesan especialmente p95, p99 y maximo, porque muestran la experiencia de las peticiones que quedan al final de la cola.

### Resultado esperado

Con 60 intentos y 30 unidades:

- Aproximadamente 30 compras terminan en `success`.
- Las restantes terminan en `sold_out`.
- No debe haber sobreventa.
- Las latencias no son iguales: las primeras transacciones avanzan antes y otras esperan.

### Interpretacion docente

PostgreSQL resuelve correctamente el conflicto: serializa las modificaciones sobre la fila caliente. Esa serializacion es buena para la consistencia, pero mala para la latencia bajo carga.

Una forma sencilla de explicarlo en clase:

> La fila de inventario se comporta como una caja con una sola ventanilla. Pueden llegar muchos clientes a la vez, pero solo uno puede modificar el stock en cada instante.

No hay corrupcion de datos. El coste visible es la cola.

## 5. Paso 5 — Analisis tecnico de locks y sesiones bloqueadas

El paso 5 no busca que el alumno memorice todas las columnas de `pg_locks`. Busca que vea que la espera no es abstracta: hay sesiones reales, queries reales y locks reales.

### Que se pretende hacer

Este paso abre una transaccion que bloquea la fila de inventario y la mantiene abierta durante unos segundos. Despues lanza otras sesiones que intentan bloquear la misma fila. Mientras las sesiones estan esperando, el notebook consulta vistas internas de PostgreSQL.

El objetivo no es optimizar nada todavia. El objetivo es mirar dentro del motor y conectar la latencia del paso anterior con objetos tecnicos observables: sesiones, locks y procesos bloqueadores.

### Lectura del codigo

```sql
LOCK_ACTIVITY_SQL
```

Consulta `pg_stat_activity`. Esta vista responde a la pregunta: "que sesiones hay ahora mismo y que estan haciendo?".

Columnas relevantes:

- `pid`: identificador de la sesion en PostgreSQL.
- `state`: estado general de la sesion.
- `wait_event_type`: categoria de espera; en este ejercicio interesa `Lock`.
- `wait_event`: evento concreto de espera.
- `blocked_by`: lista de `pid` que bloquean a esa sesion.
- `query`: consulta que la sesion esta ejecutando o acaba de ejecutar.

```sql
LOCK_DETAIL_SQL
```

Consulta `pg_locks` y la une con `pg_stat_activity`. Esta segunda consulta responde a otra pregunta: "que locks tienen o estan esperando esas sesiones?".

Columnas relevantes:

- `locktype`: tipo de recurso bloqueado, por ejemplo `relation`, `tuple` o `transactionid`.
- `mode`: modo de lock solicitado o concedido.
- `granted`: `true` si el lock esta concedido; `false` si la sesion espera.
- `relation`: tabla o indice asociado cuando aplica.
- `transactionid`: identificador de transaccion esperado cuando la espera se expresa a nivel de transaccion.

```python
blocker_ready = asyncio.Event()
```

El evento coordina el experimento. Evita lanzar las sesiones bloqueadas antes de que la primera transaccion haya tomado el lock.

```python
async def blocker():
    conn = await pool.acquire()
    tx = conn.transaction()
    await tx.start()
    await conn.execute(
        "SELECT units_available FROM ex05_inventory WHERE product_id = $1 FOR UPDATE",
        FLASH_PRODUCT_ID,
    )
    blocker_ready.set()
    await asyncio.sleep(3)
    await tx.rollback()
```

`blocker` es la sesion que provoca la espera. Abre una transaccion manualmente, bloquea la fila del producto flash con `FOR UPDATE`, avisa de que el lock ya existe y mantiene la transaccion abierta tres segundos. Al final hace `ROLLBACK` porque no se quiere cambiar el dato; solo se quiere demostrar el bloqueo.

```python
async def waiter():
    await blocker_ready.wait()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT units_available FROM ex05_inventory WHERE product_id = $1 FOR UPDATE",
                FLASH_PRODUCT_ID,
            )
```

`waiter` representa sesiones que intentan entrar en la misma seccion critica. Quieren bloquear la misma fila. Como `blocker` aun no ha terminado, PostgreSQL las deja esperando.

```python
waiter_tasks = [asyncio.create_task(waiter()) for _ in range(3)]
await asyncio.sleep(0.5)
```

Se crean tres sesiones bloqueadas y se espera medio segundo para dar tiempo a que lleguen al lock. Esa pausa permite tomar una fotografia de PostgreSQL mientras el problema esta ocurriendo.

```python
activity_rows = await conn.fetch(LOCK_ACTIVITY_SQL)
lock_rows = await conn.fetch(LOCK_DETAIL_SQL)
```

Estas consultas capturan la evidencia tecnica. `activity_df` muestra quien esta activo o esperando. `locks_df` muestra locks concedidos y solicitados.

Terminos clave:

- `pg_stat_activity`: vista de sesiones conectadas a PostgreSQL. Permite ver `pid`, `state`, query actual y eventos de espera.
- `pid`: identificador del backend que atiende una conexion. Sirve para relacionar sesiones y detectar quien bloquea a quien.
- `state`: estado de la sesion. Ejemplos relevantes: `active`, `idle`, `idle in transaction`.
- `wait_event_type`: categoria de espera. En este ejercicio esperamos ver `Lock` cuando una sesion esta bloqueada.
- `wait_event`: evento concreto. Puede indicar el tipo de recurso esperado.
- `pg_locks`: vista de locks retenidos o solicitados.
- `granted`: `true` si el lock ya fue concedido; `false` si la sesion esta esperando.
- `relation`: lock asociado a una relacion, normalmente tabla o indice.
- `transactionid`: lock asociado a una transaccion. Es frecuente cuando una transaccion espera a que otra confirme o haga rollback.
- `tuple`: lock asociado a una fila concreta, aunque no siempre aparece de forma intuitiva para el alumno porque parte de la espera se expresa como espera sobre transaction id.
- `pg_blocking_pids(pid)`: funcion que devuelve los `pid` que estan bloqueando a una sesion.

Lectura docente esperada:

- Una sesion mantiene un lock porque hizo `SELECT ... FOR UPDATE` o `UPDATE` dentro de una transaccion abierta.
- Otra sesion intenta modificar o bloquear la misma fila.
- PostgreSQL no le permite avanzar hasta saber si la primera transaccion confirma o revierte.
- El resultado es una espera visible como `wait_event_type = 'Lock'`.

Interpretacion operacional:

La fila no esta corrupta ni PostgreSQL esta "colgado". El motor esta aplicando aislamiento y consistencia. El dolor es que, bajo trafico real, esa espera se convierte en latencia y reduce throughput.

## 6. Paso 6 — Deadlock determinista

### Que se pretende hacer

El paso 6 muestra un caso distinto a una espera normal. En una espera normal, una transaccion espera y acabara avanzando cuando la primera libere el lock. En un deadlock, dos transacciones quedan esperando una por la otra y no existe un orden natural que permita resolverlo sin abortar a alguien.

El notebook fuerza un deadlock con dos compras multiproducto:

- Transaccion A bloquea primero producto 1 y luego intenta producto 2.
- Transaccion B bloquea primero producto 2 y luego intenta producto 1.

### Lectura del codigo

```python
async def lock_two_products(label, first_product_id, second_product_id):
```

La funcion representa una transaccion que necesita dos recursos. El orden se pasa como parametro para poder crear dos transacciones con orden opuesto.

```python
await conn.execute("SET deadlock_timeout = '200ms'")
```

`deadlock_timeout` indica cuanto espera PostgreSQL antes de comprobar si hay un ciclo de deadlock. Se reduce para que el ejercicio no tarde demasiado. En un sistema real no se suele ajustar por transaccion para la logica de negocio; aqui se usa con finalidad didactica.

```python
async with conn.transaction():
```

Ambos locks se toman dentro de la misma transaccion. Eso significa que el primer lock no se libera antes de intentar el segundo.

```python
await conn.execute(
    "SELECT units_available FROM ex05_inventory WHERE product_id = $1 FOR UPDATE",
    first_product_id,
)
await asyncio.sleep(0.4)
await conn.execute(
    "SELECT units_available FROM ex05_inventory WHERE product_id = $1 FOR UPDATE",
    second_product_id,
)
```

La primera consulta bloquea un producto. El `sleep` da tiempo a que la otra transaccion bloquee el otro producto. Despues cada una intenta bloquear el recurso que ya tiene la otra.

```python
deadlock_results = await asyncio.gather(
    lock_two_products("A: producto 1 -> producto 2", 1, 2),
    lock_two_products("B: producto 2 -> producto 1", 2, 1),
)
```

`asyncio.gather` lanza ambas transacciones en paralelo. La clave es que el orden de recursos es inverso.

### Resultado esperado

Una transaccion deberia terminar como `committed` y la otra como `aborted` con un error parecido a `DeadlockDetected`.

### Interpretacion docente

PostgreSQL no "elige mal". Detecta que hay un ciclo imposible:

```text
A tiene producto 1 y espera producto 2.
B tiene producto 2 y espera producto 1.
```

Si no abortase una transaccion, ambas podrian esperar indefinidamente. Por eso PostgreSQL cancela una de ellas. La aplicacion debe capturar ese error y decidir si puede reintentar.

La complejidad relacional aparece porque la transaccion no toca una unica fila aislada. Toca varias filas que representan recursos compartidos. En cuanto existen transacciones multiproducto, devoluciones, reservas, carritos, cupones o promociones combinadas, el orden de acceso a filas empieza a ser parte del diseno.

## 7. Paso 7 — Mitigacion con orden consistente y `SELECT ... FOR UPDATE`

### Que se pretende hacer

El paso 7 aplica una mitigacion clasica: si una transaccion necesita bloquear varios recursos, la aplicacion debe bloquearlos siempre en el mismo orden canonico. En el notebook, el orden canonico es `product_id` ascendente.

Esto no elimina la contencion. Si dos transacciones quieren los mismos productos, una puede seguir esperando. Lo que elimina es el ciclo de espera que produce el deadlock.

### Lectura del codigo

```python
ordered_ids = sorted(requested_product_ids)
```

Aunque el usuario o la operacion pidan productos en cualquier orden, la aplicacion normaliza el orden antes de tocar la base de datos.

```sql
SELECT product_id, units_available
FROM ex05_inventory
WHERE product_id = ANY($1::int[])
ORDER BY product_id
FOR UPDATE
```

La consulta bloquea todas las filas necesarias y las pide ordenadas por `product_id`. La intencion es que todas las transacciones compitan por los locks en la misma secuencia.

```python
await asyncio.sleep(0.4)
```

La pausa vuelve a hacer visible la espera. Si una transaccion toma los locks primero, la otra puede esperar, pero no deberia aparecer deadlock.

```python
ordered_results = await asyncio.gather(
    lock_products_in_consistent_order("A pide 1 -> 2", [1, 2]),
    lock_products_in_consistent_order("B pide 2 -> 1", [2, 1]),
)
```

Las dos operaciones llegan con orden de negocio distinto. Aun asi, internamente ambas bloquean en el mismo orden: `[1, 2]`.

### Resultado esperado

Las dos transacciones deberian terminar como `committed`. La columna `requested_order` muestra el orden pedido por la operacion. La columna `locked_order` muestra el orden real usado para bloquear.

### Interpretacion docente

El patron reduce una clase concreta de errores: deadlocks por orden inconsistente. No convierte PostgreSQL en un sistema sin esperas. La fila o conjunto de filas sigue siendo compartido y solo una transaccion puede modificar cada recurso critico a la vez.

Este paso permite separar dos ideas que suelen confundirse:

- **Contencion:** varias transacciones quieren el mismo recurso. Puede producir espera aunque todo este bien disenado.
- **Deadlock:** varias transacciones quieren varios recursos en orden incompatible. Produce un ciclo y PostgreSQL debe abortar una transaccion.

## 8. `SELECT ... FOR UPDATE`

`SELECT ... FOR UPDATE` lee filas y, al mismo tiempo, toma locks de escritura sobre ellas hasta el final de la transaccion. Es una forma explicita de decir:

> Voy a basar una decision de negocio en estas filas y despues las voy a actualizar; nadie debe modificarlas entre mi lectura y mi escritura.

Ejemplo sencillo:

```sql
BEGIN;

SELECT units_available
FROM ex05_inventory
WHERE product_id = 1
FOR UPDATE;

-- La aplicacion comprueba si hay stock.
-- Mientras esta transaccion siga abierta, otra transaccion que intente
-- actualizar ese mismo inventario tendra que esperar.

UPDATE ex05_inventory
SET units_available = units_available - 1
WHERE product_id = 1;

COMMIT;
```

Sin ese bloqueo explicito, una aplicacion puede leer un valor y tomar una decision sobre una version que deja de ser valida antes del `UPDATE`. PostgreSQL puede seguir protegiendo escrituras con locks al actualizar, pero `FOR UPDATE` hace explicito el tramo critico: desde la lectura de negocio hasta la escritura.

Ejemplo con dos productos:

```sql
BEGIN;

SELECT product_id, units_available
FROM ex05_inventory
WHERE product_id IN (1, 2)
ORDER BY product_id
FOR UPDATE;

-- Se bloquean las filas 1 y 2 siempre en el mismo orden.
-- Si todas las transacciones siguen ese orden, se evita el ciclo de espera.

COMMIT;
```

Punto clave:

- `FOR UPDATE` no elimina la espera.
- `FOR UPDATE` ayuda a hacer explicito y ordenado quien puede modificar las filas.
- Si varias transacciones bloquean recursos en distinto orden, puede haber deadlock.
- Si todas las transacciones los bloquean en el mismo orden, puede haber cola, pero no ciclo.

## 9. Deadlocks

Un deadlock ocurre cuando dos o mas transacciones forman un ciclo de espera:

- A tiene el lock del producto 1 y espera el producto 2.
- B tiene el lock del producto 2 y espera el producto 1.

Ninguna puede avanzar. PostgreSQL detecta el ciclo y aborta una transaccion con un error de deadlock. La aplicacion debe capturar ese error y reintentar si la operacion es idempotente o segura de reintentar.

## 10. Mensajes docentes

- ACID protege el dato, pero coordinar escrituras cuesta.
- Un producto popular puede convertir una unica fila en cuello de botella.
- Los locks no son un bug: son el mecanismo de consistencia.
- Los deadlocks no son raros cuando se bloquean recursos en orden inconsistente.
- La mitigacion reduce errores, pero no elimina la contencion.
