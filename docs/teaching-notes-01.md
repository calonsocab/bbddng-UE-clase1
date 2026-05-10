# Teaching Notes — Ejercicio 01: Evolución de Esquema y EAV

**Ejercicio:** `exercises/ex01-schema-rigidity/exercise.ipynb`  
**Tiempo de lectura:** 15 minutos  
**Para:** Profesor que da la sesión + alumno avanzado que estudia por su cuenta

---

## 1. Concepto de fondo (explicación verbal — no en el notebook)

### 1.1 Por qué la evolución de esquema es un problema del modelo relacional

El modelo relacional exige definir el esquema antes de almacenar datos. Cada columna tiene un tipo, un nombre y un conjunto de constraints. Esto es una fortaleza (integridad, optimizaciones del planner) y una debilidad: cuando el negocio cambia, cambiar el esquema es una operación que puede interrumpir el servicio.

El framing correcto del ejercicio no es "añadir una columna". Ese es solo el primer síntoma observable. El framing correcto es:

> Mercat nació como producto B2C y ahora necesita evolucionar su modelo de usuario para soportar B2B.

En producción, esa evolución rara vez se reduce a un único `ALTER TABLE`. Suele implicar:

1. Añadir columnas nullable o una tabla por subtipo.
2. Desplegar una versión de la aplicación que empieza a escribir los campos nuevos.
3. Soportar durante un tiempo usuarios antiguos y usuarios nuevos.
4. Rellenar datos históricos por lotes.
5. Adaptar informes, validaciones e índices.
6. Endurecer constraints cuando los datos ya están completos.
7. Retirar compatibilidad antigua.

Este ejercicio no implementa una migración expand/contract completa porque eso sería otro ejercicio. Usa el `ALTER TABLE` como experimento mínimo para que el alumno vea que incluso el primer paso de una evolución toca infraestructura compartida.

**Este no es un problema específico de PostgreSQL.** Los siguientes motores tienen restricciones equivalentes:

| Motor | Comportamiento al `ADD COLUMN NOT NULL DEFAULT` |
|-------|------------------------------------------------|
| PostgreSQL ≥ 11 | Lock exclusivo de esquema durante milisegundos (fast default) |
| MySQL ≥ 8 con `ALGORITHM=INSTANT` | Similar a PG11+ para algunos casos |
| MySQL < 8 / sin INSTANT | Copia completa de la tabla, bloqueo prolongado |
| SQL Server | `WITH ONLINE` disponible pero no gratuito; sin ella, bloqueo total |
| Oracle | `DBMS_REDEFINITION` para evitar bloqueo; sin él, bloqueo total |

La conclusión es la misma en todos: **cambiar el esquema de una tabla viva en producción tiene un coste operacional**, y ese coste escala con el tráfico, no solo con el número de filas.

### 1.2 Evolución parcial: el estado incómodo entre dos modelos

Una parte crítica del aprendizaje es entender que durante una migración real conviven estados:

```text
Usuarios antiguos:
  email, first_name, last_name, user_type

Usuarios nuevos B2B:
  email, first_name, last_name, user_type,
  company_name, tax_id, industry, employees_range, account_manager
```

Durante esa transición, la aplicación y los informes tienen que leer ambos mundos. Esto genera preguntas operacionales:

- ¿Qué hace el informe semanal si `tax_id` todavía es `NULL` para usuarios antiguos?
- ¿Cuándo podemos marcar `company_name` como `NOT NULL`?
- ¿Quién rellena datos históricos y a qué ritmo?
- ¿Qué versión de la aplicación escribe campos nuevos?
- ¿Cómo hacemos rollback si el despliegue falla?

Esta es la razón por la que el ejercicio conecta con MongoDB: en la Clase 4 se verá **schema versioning**, donde distintos documentos pueden declarar explícitamente su versión de esquema. Eso no elimina la complejidad; cambia dónde vive.

### 1.3 El lock exclusivo de esquema

Cuando un motor relacional ejecuta `ALTER TABLE ADD COLUMN`, necesita garantizar que ningún proceso lea o escriba la tabla mientras modifica su definición. Para eso adquiere un **lock exclusivo de esquema** (PostgreSQL lo llama `ACCESS EXCLUSIVE`, SQL Server `SCH-M`, Oracle `DDL lock`).

Este lock bloquea **absolutamente todo**: lecturas, escrituras, SELECTs. Mientras está activo:

- Todas las queries entrantes quedan encoladas en el pool de conexiones
- Si el lock dura más que el `statement_timeout` de los clientes, empiezan los timeouts
- Con un pool de 200 conexiones y queries cortas (5ms), en 3ms de lock pueden llegar 10-15 queries nuevas → todas esperan

```
Timeline de un ALTER TABLE en producción (tráfico alto):
  t=0.000  ALTER TABLE recibe el comando
  t=0.001  Intenta adquirir el lock exclusivo de esquema
           → Si hay una transacción activa de larga duración: espera
           → Si no hay: adquiere el lock inmediatamente
  t=0.003  [PG16 con fast default]: Lock liberado — 3ms en total
  t=0.003  Las ~10 queries que llegaron durante esos 3ms se ejecutan en ráfaga
  
  ESCENARIO CONVOY (hay una transacción activa cuando llega el ALTER):
  t=0.000  ALTER TABLE llega → espera por la transacción activa
  t=3.000  Transacción larga termina → ALTER adquiere el lock
  t=3.003  ALTER completa → lock liberado
  t=3.003  Las ~600 queries que llegaron durante 3s se ejecutan en ráfaga
```

El efecto convoy es el verdadero peligro, no la duración del ALTER en sí.

### 1.4 El fast default de PostgreSQL 11+ (para referencia — explícalo de palabra)

En PG11, se introdujo una optimización: en lugar de reescribir las filas para añadir la columna, el motor almacena el valor del DEFAULT en el catálogo del sistema y lo aplica al vuelo cuando la fila se lee. Resultado: el lock dura milisegundos en lugar de minutos.

**Limitación clave:** funciona solo si el DEFAULT es un valor constante (`'Individual'`, `0`, `false`). Si es no-determinista (`now()`, `gen_random_uuid()`), el motor aún tiene que reescribir las filas.

Esta distinción es relevante para el alumno porque explica por qué la duración del lock no depende del número de filas cuando el DEFAULT es constante.

### 1.5 El anti-patrón EAV (Entity-Attribute-Value)

Cuando los equipos se encuentran con la rigidez del esquema, la "solución" más común es guardar atributos como filas en lugar de columnas:

```sql
-- Esquema normalizado (rígido):
SELECT company_name FROM ex01_users WHERE id = 42;

-- EAV (flexible pero costoso):
SELECT attr_value FROM ex01_user_attributes
WHERE user_id = 42 AND attr_name = 'company_name';
```

**Consecuencias para el optimizador:**

1. **Estadísticas inútiles**: el planner analiza `attr_value` como una columna única que mezcla URLs, números, códigos y texto libre. No puede saber que cuando `attr_name = 'loyalty_tier'` solo hay 4 valores posibles, pero cuando `attr_name = 'portfolio_url'` los valores son todos únicos. Las estimaciones de cardinalidad son sistemáticamente erróneas → planes subóptimos.

2. **Reconstrucción obligatoria de objetos**: recuperar N atributos requiere pivotar filas a columnas (`GROUP BY` + `MAX(CASE WHEN ...)`) o hacer N JOINs contra la misma tabla de atributos. En ambos casos el modelo físico ya no se parece al modelo mental del negocio.

3. **Pérdida de tipos y constraints**: todo es `TEXT`. No hay `NOT NULL` por atributo, no hay FOREIGN KEY a otras tablas, no hay CHECK que garantice que los usuarios B2B siempre tienen `company_name`.

---

## 2. Adaptación para clase online

Este ejercicio está diseñado para ejecutarse de forma autónoma sin instructor presente. Los puntos de interacción con el profesor son:

### Paso 2 — Poll (Kahoot / Teams)

Lanza la encuesta antes de que los alumnos ejecuten las celdas de código. Las preguntas ya no están embebidas en el notebook para no convertirlo en un documento de evaluación. Están preparadas en:

```text
docs/kahoot-ex01.md
```

Ese fichero contiene enunciados, opciones, respuesta correcta y explicación breve para Kahoot, Teams Polls o trabajo asíncrono.

**Respuestas correctas:**

- **Pregunta A** — "¿Cuánto tarda `ALTER TABLE ADD COLUMN NOT NULL DEFAULT`?"  
  → **d) Depende de la versión de la base de datos** (en PG16: < 1 segundo; en versiones antiguas: minutos)

- **Pregunta B** — "¿Pueden otras queries leer durante el ALTER?"  
  → **b) No, si el ALTER obtiene o espera un lock exclusivo, las operaciones nuevas pueden quedar en cola** (el punto es el convoy, no solo el lock breve)

- **Pregunta C** — "¿Por qué EAV puede parecer atractivo durante una evolución de esquema?"  
  → **b) Posibilidad de añadir atributos sin modificar el esquema** (aunque con consecuencias severas)

**Timing sugerido:** lanza el poll justo después de que el alumno haya leído el Paso 1. Espera 3-4 minutos para respuestas antes de revelar resultados. Los resultados del poll sirven de hilo conductor para la explicación oral.

Al final del notebook, usa el bloque **Mini-quiz final** del mismo fichero para comprobar comprensión. En diferido, el alumno puede abrir `docs/kahoot-ex01.md`, responder en papel y luego contrastar con `solution.md`.

### Puntos de discusión asíncrona (foro / Teams)

Si el formato lo permite, estas preguntas funcionan bien como discusión post-ejercicio:

- *"¿En qué situación usarías EAV conscientemente a pesar de sus problemas?"*
- *"¿Cuándo un lock de 3ms puede colapsar un sistema con 200 conexiones?"*

---

## 3. Recorrido por el ejercicio

### Paso 3 — Exploración del dataset

Las celdas son completas (sin `___`). El alumno solo ejecuta y observa. Esto es intencional: en este ejercicio Jupyter no debe funcionar como una terminal SQL para practicar sintaxis, sino como un laboratorio guiado para observar comportamiento.

La primera celda de setup elimina columnas/tablas creadas por ejecuciones anteriores. En formato online esto es clave: muchos alumnos reejecutan notebooks a medias, cierran el portátil y vuelven al día siguiente. El ejercicio debe ser idempotente.

Los puntos de atención:

- La distribución 60/30/10 (b2c/b2b/freelancer) es intencional: simula una plataforma que empezó como B2C y fue añadiendo segmentos
- Los atributos EAV muestran valores realistas: `company_name` = nombre de empresa real (Faker), `tax_id` = CIF formato B12345678, `industry` = sector de una lista curada

### Paso 4A — ALTER TABLE fast default

El alumno mide una operación de pocos milisegundos en PG16. El punto pedagógico no es la rapidez — es que **el primer paso de la evolución ya toca el esquema compartido**. La celda markdown posterior lo explica. No hace falta entrar en xmin/xmax o en el mecanismo interno de PG11.

Frase útil:

> Este `ALTER` no es "la migración B2B completa"; es la pieza mínima observable de una evolución mayor.

### Paso 4B — Demo del efecto convoy (Python con threads)

Esta celda es autocontenida: simula una transacción activa de 3 segundos que **lee `ex01_users`**, un `ALTER TABLE` que llega medio segundo después y un `SELECT` normal que llega cuando el `ALTER` ya está esperando. El detalle importante es que la transacción larga toca la tabla; si solo ejecutase `pg_sleep(3)`, no bloquearía el `ALTER`.

#### Qué demuestra exactamente

La demo no pretende demostrar que cualquier `ALTER TABLE` siempre bloquee durante segundos. En PostgreSQL 16, el `ADD COLUMN DEFAULT constante` normalmente dura milisegundos. Lo que demuestra es una situación operacional concreta:

1. Ya existe una transacción leyendo la tabla.
2. Llega un `ALTER TABLE` que necesita lock exclusivo de esquema.
3. Mientras el `ALTER TABLE` espera, llega una query normal.
4. Esa query normal queda detrás del `ALTER`, aunque normalmente podría convivir con la primera lectura.

El aprendizaje es: **el riesgo no es solo la duración propia del ALTER; es el orden en el que llega respecto al tráfico vivo**.

El resultado esperado:

```
El ALTER esperó ~2.5 segundos por la transacción activa
El SELECT normal esperó ~2.0 segundos detrás del ALTER
```

#### Por qué hay `time.sleep(0.5)`

Los `sleep` no hacen lento a PostgreSQL. Sirven para construir una línea de tiempo determinista en una demo con hilos:

```
t=0.0s  empieza la transacción larga y toca ex01_users
t=0.5s  llega el ALTER TABLE
t=1.0s  llega el SELECT normal
t=3.0s  termina la transacción larga
```

Sin esos `sleep`, los tres hilos arrancan casi a la vez, pero el sistema operativo puede ejecutarlos en cualquier orden. Puede ocurrir que el `ALTER TABLE` entre antes de que la transacción larga haya tocado `ex01_users`. En ese caso el ALTER termina en milisegundos y el SELECT también:

```
Tiempo observado del ALTER TABLE : 0.0 s
Tiempo observado del SELECT normal: 0.0 s
```

Ese resultado no contradice la teoría. Solo significa que no se creó el convoy. La condición necesaria para el convoy es el orden:

```
transacción larga activa -> ALTER esperando -> SELECT nuevo detrás
```

#### Cómo explicar los tiempos

Si la transacción dura 3 segundos:

- El `ALTER` llega en `t=0.5s`, así que espera aproximadamente `3.0 - 0.5 = 2.5s`.
- El `SELECT` normal llega en `t=1.0s`, así que espera aproximadamente `3.0 - 1.0 = 2.0s`.

El `SELECT` no tarda 2 segundos porque contar usuarios B2B sea caro. Tarda 2 segundos porque queda en la cola de locks detrás del `ALTER`.

#### Mensaje pedagógico para reforzar

La query larga por sí sola no bloquea todas las lecturas. Muchas queries podrían leer al mismo tiempo sin problema. El problema aparece cuando llega una operación de cambio de esquema que necesita exclusividad. A partir de ese momento, el sistema empieza a ordenar las operaciones alrededor de ese lock exclusivo, y las nuevas queries pueden quedar esperando aunque sean lecturas inocentes.

Lo importante es que observe la cadena completa:

```
query larga -> ALTER esperando -> SELECT normal esperando detrás
```

### Paso 4C — EAV como intento de evitar migraciones frecuentes

El alumno ejecuta dos queries en Python y compara tiempos usando mediana de varias repeticiones. La comparación ya no es EAV contra "una columna suelta", sino EAV contra una alternativa relacional equivalente: una tabla por subtipo `ex01_user_b2b_profile`.

#### Qué está pasando conceptualmente

La petición de negocio es deliberadamente sencilla:

> "Necesito un informe semanal de clientes B2B con empresa, NIF, sector y responsable de cuenta."

En el modelo mental del negocio, esos campos son columnas de un cliente B2B. Pero en EAV no existen como columnas; existen como filas:

```text
user_id | attr_name       | attr_value
--------+-----------------+-------------------------
14      | company_name    | Chaparro & Asociados
14      | tax_id          | B23043725
14      | industry        | Consultoría
14      | account_manager | Almudena Castellanos
```

Por eso la query EAV tiene que reconstruir el perfil haciendo varios JOINs contra la misma tabla:

```sql
LEFT JOIN ex01_user_attributes company
    ON company.user_id = u.id
   AND company.attr_name = 'company_name'
LEFT JOIN ex01_user_attributes tax
    ON tax.user_id = u.id
   AND tax.attr_name = 'tax_id'
LEFT JOIN ex01_user_attributes industry
    ON industry.user_id = u.id
   AND industry.attr_name = 'industry'
LEFT JOIN ex01_user_attributes manager
    ON manager.user_id = u.id
   AND manager.attr_name = 'account_manager'
```

La frase para el aula:

> En EAV, cada columna de negocio se convierte en una búsqueda dentro de una tabla genérica.

La tabla por subtipo representa una alternativa relacional clásica:

```text
ex01_users
  id
  email
  user_type
  ...

ex01_user_b2b_profile
  user_id
  company_name
  tax_id
  industry
  account_manager
  employees_range
```

Esto sigue siendo relacional. No es una solución NoSQL. Su valor pedagógico es mostrar que el modelo relacional tiene una respuesta mejor que EAV: modelar explícitamente el subtipo B2B con columnas reales.

La query resultante se parece mucho más al lenguaje del negocio:

```sql
SELECT user_id, email, company_name, tax_id, industry, account_manager
FROM ex01_user_b2b_profile;
```

El ratio EAV/relacional esperado con 1M usuarios (modo `--small`):

- EAV (4 JOINs sobre la tabla de atributos): 120ms - 250ms
- Relacional por subtipo: 25ms - 70ms
- **Ratio típico: 2x - 6x**

El número exacto no es el aprendizaje principal. La clave es que el alumno vea:

- La query EAV es mucho más larga
- La misma tabla de atributos aparece varias veces
- Las columnas de negocio (`industry`, `tax_id`, etc.) no existen como columnas reales
- El planner tiene menos información semántica para estimar cardinalidades

#### Por qué enseñar la tabla por subtipo si la clase trata de debilidades relacionales

Es importante evitar una conclusión simplista:

> "Relacional es malo, EAV es malo, entonces NoSQL es bueno."

La conclusión correcta es más madura:

> El modelo relacional tiene buenas herramientas para modelar el dominio, pero esas herramientas siguen obligando a negociar con el esquema cuando el negocio cambia.

La tabla por subtipo enseña dos cosas a la vez:

1. **EAV no es la única respuesta dentro de PostgreSQL.** Un buen modelado relacional puede evitar muchas de sus patologías.
2. **La rigidez de esquema no desaparece.** Si mañana producto pide otro campo B2B, hay que volver a hacer `ALTER TABLE`, aunque sea sobre una tabla más pequeña.

Este matiz es valioso para un máster: el alumno ve que no se trata de caricaturizar SQL, sino de entender tradeoffs.

#### Costes de la tabla por subtipo

La tabla por subtipo también tiene consecuencias negativas:

1. **Sigue requiriendo `ALTER TABLE`**

   Si mañana producto pide `billing_contact_email`, hay que ejecutar:

   ```sql
   ALTER TABLE ex01_user_b2b_profile
   ADD COLUMN billing_contact_email TEXT;
   ```

   Es mejor que alterar `ex01_users` si la tabla B2B es más pequeña, pero el problema operacional no desaparece.

2. **Aumenta el número de tablas**

   Un sistema real puede acabar con:

   ```text
   ex01_users
   ex01_user_b2b_profile
   ex01_user_freelancer_profile
   ex01_user_seller_profile
   ex01_user_partner_profile
   ```

   Esto mejora el modelado, pero fragmenta el dominio.

3. **Necesita JOINs para reconstruir perfiles completos**

   Para ver el usuario completo:

   ```sql
   SELECT *
   FROM ex01_users u
   JOIN ex01_user_b2b_profile b ON b.user_id = u.id;
   ```

   No es un problema grave, pero sí añade acoplamiento entre tablas.

4. **Hay que mantener consistencia entre `user_type` y la tabla subtipo**

   Si `ex01_users.user_type = 'b2b'`, debería existir una fila en `ex01_user_b2b_profile`. Esa regla no siempre es trivial de expresar con constraints simples. Puede requerir triggers, validaciones en aplicación o procesos de auditoría.

5. **Puede degenerar en muchas columnas nullable**

   Si los atributos B2B varían por país, vertical, integración o cliente enterprise, la tabla subtipo puede crecer con muchas columnas opcionales:

   ```text
   vat_number
   billing_email
   crm_account_id
   sap_id
   erp_code
   custom_segment
   ...
   ```

   Aquí vuelve la tensión original: o se añaden columnas constantemente, o se busca una estructura más flexible.

La frase de cierre:

> La tabla por subtipo es mejor diseño relacional que EAV, pero sigue viviendo dentro del mundo de migraciones, DDL y coordinación de esquema.

### Paso 5 — Modifica y observa

El alumno pasa de listar clientes a filtrar por dos atributos: `industry = 'Tecnología'` y `employees_range = '201-1000'`.

#### Qué cambia respecto al Paso 4C

En Paso 4C queríamos listar atributos. En Paso 5 queremos filtrar por varios atributos a la vez.

Esto es más exigente para EAV. La condición de negocio:

```sql
industry = 'Tecnología'
AND employees_range = '201-1000'
```

no vive en una sola fila EAV. Vive en dos filas distintas del mismo usuario:

```text
user_id | attr_name       | attr_value
--------+-----------------+------------
14      | industry        | Tecnología
14      | employees_range | 201-1000
```

Por eso la query EAV necesita juntar la tabla de atributos consigo misma:

```sql
JOIN ex01_user_attributes industry
    ON industry.user_id = u.id
   AND industry.attr_name = 'industry'
   AND industry.attr_value = 'Tecnología'

JOIN ex01_user_attributes employees
    ON employees.user_id = u.id
   AND employees.attr_name = 'employees_range'
   AND employees.attr_value = '201-1000'
```

La frase para el aula:

> En EAV, cada atributo filtrado se convierte en otra relación que hay que juntar.

En la tabla por subtipo, la misma condición es natural:

```sql
WHERE industry = 'Tecnología'
  AND employees_range = '201-1000'
```

Y además puede tener un índice compuesto:

```sql
CREATE INDEX ON ex01_user_b2b_profile(industry, employees_range);
```

Esta comparación suele mostrar una diferencia más grande que el informe:

- EAV necesita dos JOINs a la tabla de atributos, uno por cada atributo filtrado
- La tabla relacional por subtipo puede resolverlo con un índice compuesto `(industry, employees_range)`

Este paso es mejor para aprendizaje autónomo que "añade un quinto atributo y mira si tarda más", porque las mediciones de añadir un atributo pueden variar por caché y producir el efecto contrario en portátiles pequeños.

#### Qué debe llevarse el alumno de Paso 5

El aprendizaje no es solo "EAV es más lento". Es más específico:

- EAV rompe la correspondencia entre atributo de negocio y columna física.
- El optimizador ve una tabla genérica de atributos, no un modelo rico con columnas `industry` y `employees_range`.
- Los índices naturales del problema (`industry, employees_range`) no aparecen de forma directa.
- La query se vuelve menos legible para analytics y más difícil de mantener.

La conexión con rigidez de esquema:

> EAV evita el dolor inicial del `ALTER TABLE`, pero convierte preguntas normales del negocio en consultas estructuralmente más complejas.

#### Pregunta esperable: "¿Por qué no usamos una vista?"

Es una pregunta muy buena y conviene anticiparla. Un alumno con criterio puede decir:

> "Si la query EAV es fea, ¿por qué no creamos una vista que la esconda?"

Ejemplo:

```sql
CREATE VIEW ex01_user_b2b_view AS
SELECT
    u.id,
    u.email,
    company.attr_value AS company_name,
    tax.attr_value AS tax_id,
    industry.attr_value AS industry,
    manager.attr_value AS account_manager
FROM ex01_users u
LEFT JOIN ex01_user_attributes company
    ON company.user_id = u.id
   AND company.attr_name = 'company_name'
LEFT JOIN ex01_user_attributes tax
    ON tax.user_id = u.id
   AND tax.attr_name = 'tax_id'
LEFT JOIN ex01_user_attributes industry
    ON industry.user_id = u.id
   AND industry.attr_name = 'industry'
LEFT JOIN ex01_user_attributes manager
    ON manager.user_id = u.id
   AND manager.attr_name = 'account_manager'
WHERE u.user_type = 'b2b';
```

La respuesta corta:

> Una vista mejora la ergonomía, pero no cambia el coste físico.

Una vista normal en PostgreSQL es básicamente una query guardada. Cuando el alumno ejecuta:

```sql
SELECT *
FROM ex01_user_b2b_view;
```

PostgreSQL expande la vista y ejecuta por debajo la query con los JOINs. La vista ayuda a no repetir SQL feo y a dar a analytics una interfaz más cómoda, pero no elimina:

- que los atributos sigan siendo filas
- que haya que reconstruir columnas
- que los tipos sigan siendo `TEXT`
- que los constraints por atributo sigan siendo débiles
- que filtrar por varios atributos siga requiriendo lógica EAV
- que el planner siga trabajando sobre una tabla genérica de atributos

La frase útil para clase:

> Vista normal = esconder complejidad, no eliminar complejidad.

#### "¿Y una vista materializada?"

Una vista materializada sí guarda el resultado:

```sql
CREATE MATERIALIZED VIEW ex01_user_b2b_mv AS
SELECT ...
```

Esto puede acelerar lecturas, pero transforma el problema:

- Los datos pueden quedar obsoletos.
- Hay que refrescar la vista.
- `REFRESH MATERIALIZED VIEW` tiene coste operacional.
- Para refresco concurrente necesitas índice único y más diseño.
- Sigues teniendo que decidir qué atributos entran en la vista.
- Si producto añade un atributo nuevo, tienes que cambiar la vista materializada y probablemente sus índices.

Por tanto:

> Vista materializada = proyección/copia derivada que hay que mantener.

Esto ya se parece a una tabla wide, una cache, una proyección analítica o una desnormalización controlada. Puede ser una solución razonable en producción, pero no invalida el aprendizaje del ejercicio: EAV evitó el `ALTER TABLE` inicial, pero generó una estructura que luego necesita capas de compensación.

#### Cómo conectar vistas, EAV y tablas subtipo

Usa esta tabla si aparece la discusión:

| Opción | Ventaja | Coste |
|--------|---------|-------|
| EAV | Añadir atributos sin `ALTER TABLE` | Pierde tipos, constraints, queries simples e índices naturales |
| Vista normal sobre EAV | Oculta SQL repetitivo | No cambia el coste físico ni la semántica pobre |
| Vista materializada sobre EAV | Acelera lecturas | Añade refresco, staleness y otro esquema derivado |
| Tabla por subtipo | Modela el dominio con columnas reales | Sigue necesitando migraciones cuando cambia el negocio |

El cierre pedagógico:

> Relacional no falla porque no tenga soluciones. Tiene varias. El punto es que todas obligan a negociar con el esquema o con proyecciones derivadas cuando el negocio cambia.

### Paso 6 — Desafío aplicado

El objetivo es que el alumno diseñe una query deliberadamente lenta sobre EAV para interiorizar por qué los filtros multi-atributo son costosos. La celda base no falla si el alumno la ejecuta sin modificar, porque en formato online los errores "vacíos" se perciben como rotura del material, no como invitación a participar.

---

## 4. Preguntas socráticas para el aula

**Pregunta 1:** *"El ALTER tardó 3ms. En producción con 1000 queries por segundo, ¿cuántas queries pueden quedar bloqueadas durante esos 3ms?"*

*Orientación:* 3ms × 1000 qps = 3 queries en espera. Pero si hay una transacción larga activa, el ALTER espera (digamos 3 segundos) → 3000 queries bloqueadas. El peligro no es el ALTER en sí, es el convoy.

**Pregunta 2:** *"¿Por qué el optimizador no puede aprovechar el índice `idx_ex01_eav_name` cuando filtramos por `attr_name = 'industry' AND attr_value = 'Tecnología'`?"*

*Orientación:* El índice existe en `attr_name`, pero el predicado también usa `attr_value`. El índice en `attr_name` reduce las filas a ~1.7M (todas las filas de 'industry'), pero luego hay que filtrar por `attr_value` sin índice. Un índice en `(attr_name, attr_value)` ayudaría, pero solo para esa combinación concreta.

**Pregunta 3:** *"Si el EAV tiene todos esos problemas, ¿por qué lo sigue usando la gente?"*

*Orientación:* Porque resolver el problema "correctamente" (tabla separada por tipo de usuario, o columnas normalizadas) requiere `ALTER TABLE` — que es exactamente el problema que se intentaba evitar. El EAV es una trampa circular.

---

## 5. Errores típicos del alumno

**"El ALTER fue rápido, no entiendo cuál era el drama"**

El alumno está en PG16 con fast default. Señala la demo de convoy (4B): el drama no es la duración del ALTER sino que bloquea todo mientras corre, y si hay tráfico activo, espera.

**"¿Por qué no usamos JSONB en lugar de EAV?"**

Buena observación — el alumno está buscando soluciones. Redirigir: *"JSONB mejora EAV en varios aspectos dentro de PostgreSQL, pero hereda el problema de las estadísticas y los tipos. En la Clase 4 veremos por qué MongoDB diseñó su motor entero alrededor de este problema."*

**"¿El índice `idx_ex01_eav_user` no debería hacer rápida la query por usuario?"**

Sí, para recuperar todos los atributos de un usuario concreto. El problema aparece cuando quieres reconstruir el perfil completo de decenas de miles de usuarios B2B o filtrar por varios atributos a la vez. Ahí la tabla EAV deja de comportarse como "un lookup por usuario" y pasa a comportarse como varias relaciones genéricas que hay que juntar.

---

## 6. Conexión con el temario

Este ejercicio demuestra tres limitaciones estructurales del modelo relacional:

1. **La evolución de esquema no es una sentencia aislada.** Cada evolución del negocio requiere coordinar DDL, tráfico vivo, versiones de aplicación, datos antiguos, backfills, constraints e informes.

2. **Los cambios de esquema tienen coste operacional en sistemas vivos.** Incluso cuando el `ALTER` dura milisegundos, puede participar en un convoy de locks si llega detrás de una transacción activa.

3. **El EAV es el escape hatch del modelo relacional — y una trampa.** Los equipos inventan EAV para evitar el ALTER, pero terminan con una base de datos sin tipos, sin constraints, con planes de ejecución degradados y lógica de validación en la capa de aplicación.

La Clase 4 (MongoDB) presenta otra forma de gestionar esta tensión: documentos con formas distintas y **schema versioning**. El esquema deja de vivir solo en el catálogo de la base de datos y pasa a estar parcialmente en los documentos y en el código de aplicación. El ejercicio 08 (Live Migration) explora el patrón expand/contract como respuesta operacional dentro de PostgreSQL.

---

## 7. Lecturas opcionales

1. **"Designing Data-Intensive Applications"** — Kleppmann, Capítulo 2: evolución histórica del modelo relacional, EAV y modelos document.
2. **"SQL Antipatterns"** — Karwin, Capítulo 6: análisis exhaustivo del patrón EAV, sus variantes y cuándo (raramente) tiene sentido.
3. **Documentación de pt-online-schema-change** (Percona): la herramienta estándar para ALTER TABLE sin bloqueo en MySQL.
4. **`gh-ost` de GitHub**: equivalente para MySQL con replicación, con explicación del problema de locking que resuelve.
