# Teaching Notes — Ejercicio 03: Reporting y Preagregacion para Ventas

**Ejercicio:** `exercises/ex03-reporting-preaggregation/exercise.ipynb`  
**Tiempo de lectura:** 20 minutos  
**Para:** profesor que da la sesion + alumno avanzado que estudia por su cuenta

---

## 1. Concepto de fondo

El ejercicio 3 presenta un caso de reporting: Mercat quiere monitorizar ventas por categoria y producto en un cuadro de control tipo Power BI. La query normalizada es correcta, pero recalcula metricas de negocio desde tablas OLTP cada vez que se refresca el informe.

El objetivo no es posicionar Redis, MongoDB, Cassandra o Elasticsearch como motores de reporting. El objetivo es introducir la diferencia entre:

- modelo transaccional normalizado,
- consulta agregada de reporting,
- fuente preparada para BI: materialized view, tabla agregada, data mart o modelo tabular.

---

## 2. Recorrido por el ejercicio

### Paso 1 — Contexto

El cuadro de control pide productos, categoria, ingresos recientes, ventas recientes, clientes distintos, canal y segmento. El alumno debe entender que es una lectura agregada de negocio, no una pantalla operacional de catalogo.

### Paso 2 — Forma del informe

No hay predicciones numericas artificiales. El alumno identifica que metricas necesita el informe y que tablas alimentan esas metricas.

### Paso 3 — Dataset

Se muestran conteos de tablas. La idea a reforzar:

- `ex03_sales` acumula eventos,
- las dimensiones enriquecen el analisis,
- el resultado final puede ser pequeno aunque el trabajo intermedio sea grande.

### Paso 4 — Consulta normalizada

La query devuelve 48 productos, pero calcula metricas con JOINs y agregaciones. Si tarda 100-200 ms en local, no hay que venderlo como desastre. La lectura docente correcta es:

> "Aislada parece razonable. Repetida por usuarios, filtros y refrescos, este coste se multiplica."

### Paso 5 — Pagina de informe con varias visualizaciones

Vincularlo con un caso real: reunion semanal de ventas. El equipo comercial abre una pagina de Power BI con varias visualizaciones: top productos, ingresos, clientes distintos, ventas por canal, ventas por segmento, tendencia y comparativas.

Durante esa sesion no hay una unica consulta. Cada cambio de filtro puede disparar varias consultas. La celda usa 8 categorias repetidas 10 veces como aproximacion didactica a varias visualizaciones y varias interacciones de informe.

No presentarlo como "el usuario espera 11 s". El dolor real es:

- cada visualizacion puede tardar 100-150 ms o mas,
- una pagina tiene varias visualizaciones,
- la pagina no se percibe completa hasta que llegan las visualizaciones lentas,
- varios usuarios/refrescos elevan p95/p99 por competencia de recursos.

En la prueba local previa, el coste acumulado rondo 11 s. El numero exacto depende del equipo, pero el patron debe ser claro: no es una unica espera de usuario, es trabajo repetido que se traduce en spinners, filtros lentos y carga innecesaria sobre OLTP.

### Paso 6 — Tabla agregada

La materialized view representa una fuente preparada para reporting. No es la recomendacion final de arquitectura; es una herramienta pedagogica para comparar la misma lectura contra una tabla agregada.

En la prueba local previa:

- consulta normalizada: ~150 ms,
- consulta desde tabla agregada: ~1-3 ms,
- 80 refrescos normalizados: ~11 s,
- 80 refrescos desde tabla agregada: ~80 ms.

El valor pedagogico esta en el ratio y en el trade-off, no en el numero exacto.

---

## 3. Relacion con el ejercicio 4

El ejercicio 4, **Hot Reads & Latency**, debe quedar separado conceptualmente:

- Ejercicio 3: reporting, agregaciones, precomputo, BI, materialized views/data marts.
- Ejercicio 4: lecturas calientes, latencia p50/p95/p99, concurrencia, read models operacionales y limites de acceso repetido.

Redis encaja mucho mejor como continuacion natural del ejercicio 4 que del ejercicio 3. En esta clase no hace falta implementarlo: primero interesa ver por que PostgreSQL empieza a sufrir con lecturas calientes.

---

## 4. Preguntas socraticas

1. **Si el informe devuelve solo 48 productos, por que puede doler refrescarlo muchas veces?**  
   Porque cada refresco recalcula metricas leyendo ventas, uniendo dimensiones y agrupando.

2. **Que evita la tabla agregada?**  
   Evita repetir JOINs y agregaciones en tiempo de consulta. La lectura ya esta en la forma que necesita el informe.

3. **Que coste introduce?**  
   Duplicacion, refresco, posible desfase de datos y complejidad operacional.

4. **Por que esto no es lo mismo que cache?**  
   La cache acelera respuestas repetidas; la tabla agregada cambia la forma de los datos para reporting y puede ser parte de un pipeline BI.

---

## 5. Errores tipicos del alumno

- **"150 ms no es mucho."** Correcto para una llamada aislada; pedir que lo multiplique por usuarios, filtros, visualizaciones y refrescos.
- **"11 s / 80 usuarios = latencia real de cada usuario."** No exactamente. Es coste medio secuencial, no una prueba de concurrencia.
- **"Entonces siempre hacemos tablas agregadas."** No. Solo cuando el coste o el SLA de reporting lo justifica.
- **"Power BI deberia consultar OLTP directamente."** Puede hacerlo, pero no siempre debe hacerlo para informes pesados o frecuentes.
- **"La materialized view es la solucion final."** En este ejercicio es una forma controlada de mostrar el patron.

---

## 6. Conexion con el temario

- **Reporting/BI:** fuente preparada para cuadros de control.
- **Data marts:** tablas orientadas a consumo analitico de un area.
- **ETL/ELT:** procesos que mantienen las tablas agregadas.
- **Clase 5:** cache y latencia como problema distinto: respuestas calientes y concurrencia.

---

## 7. Lecturas opcionales

- PostgreSQL documentation: materialized views.
- Kimball & Ross, *The Data Warehouse Toolkit*, fact/dimension tables y data marts.
- Martin Kleppmann, *Designing Data-Intensive Applications*, capitulos sobre derived data.
