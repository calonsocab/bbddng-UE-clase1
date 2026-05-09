# Ejercicio 02 — Impedance Mismatch

**Tiempo estimado:** 40 minutos  
**Dificultad:** Intermedia  
**Tema de fondo:** mapping objeto-relacional, agregados de dominio, N+1, JOINs y reconstruccion de objetos

---

## Antes de abrir el notebook

Desde la raiz del repositorio:

```bash
make up
make seed-ex-02
make exercise-02
```

El comando `make exercise-02` abre este notebook:

[exercise.ipynb](exercise.ipynb)

---

## Objetivo de aprendizaje

Al terminar este ejercicio el alumno sera capaz de:

1. Explicar que significa impedance mismatch entre objetos de aplicacion y tablas relacionales.
2. Reconstruir un agregado `Order` realista desde un modelo 3NF con 6+ JOINs.
3. Identificar por que aparece el problema N+1 en ORMs y APIs.
4. Leer un `EXPLAIN (ANALYZE, BUFFERS)` de una query que recompone un objeto desde varias relaciones.
5. Discutir el tradeoff entre normalizacion, integridad y rendimiento de lectura.
6. Conectar este dolor con el modelo documental que se vera en MongoDB.

---

## Narrativa de negocio

Mercat ya no solo necesita usuarios. Ahora tiene que servir una pantalla de detalle de pedido:

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

En memoria, el pedido es un objeto natural. En PostgreSQL normalizado, ese objeto esta repartido en muchas tablas: clientes, pedidos, lineas, productos, direcciones, pagos, envios y eventos de tracking.

El ejercicio no dice que la normalizacion sea mala. Dice que, cuando la aplicacion pide un agregado completo, alguien tiene que volver a pegar todas sus piezas.

---

## Dataset

El script de seed crea estas tablas:

| Tabla | Filas small / full | Rol |
|-------|--------------------|-----|
| `ex02_customers` | 20k / 120k | Clientes |
| `ex02_products` | 1.5k / 8k | Catalogo |
| `ex02_orders` | 60k / 500k | Cabecera de pedido |
| `ex02_order_lines` | ~180k / ~1.5M | Lineas |
| `ex02_order_addresses` | ~120k / ~1M | Billing/shipping |
| `ex02_payments` | 60k / 500k | Pago |
| `ex02_shipments` | 60k / 500k | Envio |
| `ex02_tracking_events` | ~240k / ~2M | Eventos de tracking |

---

## Estructura del ejercicio

| Paso | Descripcion |
|------|-------------|
| 1 | Contexto y objetivo |
| 2 | Hipotesis previa con predicciones numericas |
| 3 | Setup y exploracion del dataset |
| 4 | Experimento guiado: reconstruccion de `Order` con 6+ JOINs |
| 5 | Modifica y observa: anchura del agregado y ventana temporal |
| 6 | Desafío aplicado: reproduce N+1 de forma controlada |
| 7 | Mini-quiz, reflexion final y pista |

El guion tecnico del profesor esta en [../../docs/teaching-notes-02.md](../../docs/teaching-notes-02.md).

---

## Pista para proximas clases

> Este ejercicio demuestra que el modelo relacional trocea agregados naturales del dominio para ganar integridad y evitar duplicacion. En la **Clase 4 (MongoDB)** veremos cuando tiene sentido guardar un agregado como documento y que costes nuevos aparecen al hacerlo.
