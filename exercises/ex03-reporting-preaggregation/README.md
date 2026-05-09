# Ejercicio 03 — Reporting y Preagregacion para Ventas

**Tiempo estimado:** 45 minutos  
**Dificultad:** Intermedia  
**Tema de fondo:** reporting, consultas agregadas, materialized views, tablas agregadas, OLTP vs BI

---

## Antes de abrir el notebook

Desde la raiz del repositorio:

```bash
make up
make seed-ex-03
make exercise-03
```

El comando `make exercise-03` abre este notebook:

[exercise.ipynb](exercise.ipynb)

---

## Objetivo de aprendizaje

Al terminar este ejercicio el alumno sera capaz de:

1. Entender por que un cuadro de control puede necesitar datos repartidos en muchas tablas.
2. Medir el coste de recalcular metricas de reporting desde un modelo OLTP normalizado.
3. Diferenciar una query correcta de una fuente adecuada para BI.
4. Comparar una lectura normalizada contra una tabla agregada preparada.
5. Entender por que herramientas como Power BI suelen alimentarse de modelos preparados, no de queries OLTP pesadas repetidas.

---

## Narrativa de negocio

Mercat quiere monitorizar ventas por categoria:

```text
Productos de una categoria, ingresos recientes, ventas recientes,
clientes distintos, canal y segmento.
```

El modelo relacional normalizado guarda ventas, clientes, productos, tiendas, fechas y promociones por separado. Eso es razonable para integridad y escrituras. El problema aparece cuando un cuadro de control recalcula continuamente la misma tabla agregada desde las tablas transaccionales.

El objetivo no es decir que PostgreSQL no sirve. El objetivo es ver por que reporting y OLTP tienen patrones de acceso distintos, y por que aparecen materialized views, tablas agregadas, data marts o procesos ETL/ELT.

---

## Dataset

El script de seed crea tablas normalizadas de producto y ventas:

| Tabla | Filas small / full | Rol |
|-------|--------------------|-----|
| `ex03_sales` | 500k / 5M | Ventas |
| `ex03_customers` | 120k / 120k | Dimension cliente |
| `ex03_products` | 12k / 12k | Dimension producto |
| `ex03_stores` | 250 / 250 | Dimension tienda/canal |
| `ex03_dates` | 730 / 730 | Dimension fecha |
| `ex03_promotions` | 80 / 80 | Dimension promocion |

---

## Estructura del ejercicio

| Paso | Descripcion |
|------|-------------|
| 1 | Contexto y objetivo |
| 2 | Que necesita responder el cuadro de control |
| 3 | Setup y exploracion del dataset |
| 4 | Consulta normalizada para el informe |
| 5 | Simular refrescos del informe |
| 6 | Crear y leer una tabla agregada para reporting |
| 7 | Mini-quiz, reflexion final y pista |

El guion tecnico del profesor esta en [../../docs/teaching-notes-03.md](../../docs/teaching-notes-03.md).

---

## Pista para proximas clases

> Este ejercicio demuestra que el modelo relacional puede calcular metricas de reporting correctamente, pero repetir ese calculo desde OLTP puede ser caro. Mas adelante veremos otros patrones de lectura, como cache de baja latencia y modelos orientados a consulta.
