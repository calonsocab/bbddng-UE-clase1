# Ejercicio 05 — Escrituras Concurrentes, Locks y ACID

**Tiempo estimado:** 45 minutos  
**Dificultad:** Intermedia  
**Tema de fondo:** ACID, row locks, waits, deadlocks, retries y orden de bloqueo

---

## Antes de abrir el notebook

Desde la raiz del repositorio:

```bash
make up
make seed-ex-05
make exercise-05
```

---

## Objetivo de aprendizaje

Al terminar este ejercicio el alumno sera capaz de:

1. Explicar por que una escritura correcta en secuencial puede degradar bajo concurrencia.
2. Observar como PostgreSQL protege la consistencia del inventario con locks.
3. Interpretar sesiones bloqueadas usando `pg_stat_activity` y `pg_locks`.
4. Provocar un deadlock determinista y entender por que PostgreSQL aborta una transaccion.
5. Usar orden consistente y `SELECT ... FOR UPDATE` como mitigacion.

---

## Narrativa de negocio

Mercat lanza una promocion flash. El producto `EX05-SKU-FLASH-001` tiene stock limitado y muchos usuarios intentan comprarlo al mismo tiempo.

El requisito de negocio es simple:

```text
No se puede vender mas stock del disponible.
```

El problema aparece cuando ese requisito se ejecuta con muchas escrituras concurrentes. PostgreSQL mantiene la consistencia, pero lo hace coordinando transacciones mediante locks, esperas y, si hay ciclos de espera, deadlocks.

---

## Dataset

| Tabla | Rol |
|-------|-----|
| `ex05_products` | Productos normales y productos flash |
| `ex05_inventory` | Stock disponible por producto |
| `ex05_customers` | Clientes que intentan comprar |
| `ex05_orders` | Pedidos creados |
| `ex05_order_items` | Lineas de pedido |
| `ex05_order_attempts` | Resultado de intentos de compra |

---

## Estructura del ejercicio

| Paso | Descripcion |
|------|-------------|
| 1 | Contexto y objetivo |
| 2 | Setup y exploracion del dataset |
| 3 | Compra secuencial |
| 4 | Compras concurrentes sobre el mismo producto |
| 5 | Observar locks y sesiones bloqueadas |
| 6 | Deadlock determinista |
| 7 | Mitigacion con orden consistente y `SELECT ... FOR UPDATE` |
| 8 | Cierre y reflexion |

El guion tecnico del profesor esta en [../../docs/teaching-notes-05.md](../../docs/teaching-notes-05.md).
