"""
Seed — Ejercicio 05: escrituras concurrentes, locks y ACID.

Genera un caso de promocion flash en Mercat:
  - varios productos con inventario limitado,
  - clientes que intentan comprar al mismo tiempo,
  - tablas de pedidos e intentos para observar resultados.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.pg_loader import DEFAULT_DSN, PGLoader

SEED = 47
rng = np.random.default_rng(SEED)

SMALL_CUSTOMERS = 1_000
FULL_CUSTOMERS = 10_000

DDL = """
DROP TABLE IF EXISTS ex05_order_attempts CASCADE;
DROP TABLE IF EXISTS ex05_order_items CASCADE;
DROP TABLE IF EXISTS ex05_orders CASCADE;
DROP TABLE IF EXISTS ex05_inventory CASCADE;
DROP TABLE IF EXISTS ex05_customers CASCADE;
DROP TABLE IF EXISTS ex05_products CASCADE;

CREATE TABLE ex05_products (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    is_flash BOOLEAN NOT NULL
);

CREATE TABLE ex05_inventory (
    product_id INTEGER PRIMARY KEY REFERENCES ex05_products(id),
    units_available INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE ex05_customers (
    id INTEGER PRIMARY KEY,
    segment TEXT NOT NULL,
    region TEXT NOT NULL
);

CREATE TABLE ex05_orders (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES ex05_customers(id),
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE ex05_order_items (
    order_id BIGINT NOT NULL REFERENCES ex05_orders(id),
    product_id INTEGER NOT NULL REFERENCES ex05_products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE ex05_order_attempts (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES ex05_customers(id),
    product_id INTEGER NOT NULL REFERENCES ex05_products(id),
    result TEXT NOT NULL,
    error_message TEXT,
    latency_ms NUMERIC(12,2),
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
"""

INDEX_DDL = """
CREATE INDEX idx_ex05_orders_customer ON ex05_orders(customer_id);
CREATE INDEX idx_ex05_attempts_product_result ON ex05_order_attempts(product_id, result);
CREATE INDEX idx_ex05_attempts_created ON ex05_order_attempts(created_at);
"""

PRODUCTS = [
    (1, "EX05-SKU-FLASH-001", "Consola Mercat Play Flash", 399.00, True),
    (2, "EX05-SKU-FLASH-002", "Pack Auriculares Pro Flash", 129.00, True),
    (3, "EX05-SKU-FLASH-003", "Monitor Gaming Flash", 249.00, True),
    (4, "EX05-SKU-NORMAL-004", "Teclado Mecanico", 89.00, False),
    (5, "EX05-SKU-NORMAL-005", "Raton Inalambrico", 39.00, False),
]

INITIAL_STOCK = [
    (1, 30),
    (2, 30),
    (3, 30),
    (4, 500),
    (5, 500),
]

SEGMENTS = ["consumer", "vip", "business"]
REGIONS = ["Norte", "Sur", "Este", "Oeste", "Centro", "Online"]


def _customers(n):
    for customer_id in range(1, n + 1):
        yield (
            customer_id,
            rng.choice(SEGMENTS, p=[0.82, 0.12, 0.06]),
            rng.choice(REGIONS),
        )


def run(small: bool = False, dsn: str = DEFAULT_DSN):
    n_customers = SMALL_CUSTOMERS if small else FULL_CUSTOMERS
    mode = "SMALL" if small else "FULL"
    print(f"[ex05] Modo {mode}: {n_customers:,} clientes, inventario flash limitado")

    with PGLoader(dsn) as loader:
        print("[ex05] Creando esquema...")
        loader.execute(DDL)
        loader.conn.commit()

        print("[ex05] Insertando productos e inventario...")
        loader.copy_csv("ex05_products", PRODUCTS, ["id", "sku", "name", "price", "is_flash"])
        loader.copy_csv("ex05_inventory", INITIAL_STOCK, ["product_id", "units_available"])
        loader.conn.commit()

        print("[ex05] Insertando clientes...")
        loader.copy_csv_chunked(
            "ex05_customers",
            _customers(n_customers),
            ["id", "segment", "region"],
            50_000,
            n_customers,
            "customers",
        )

        print("[ex05] Creando indices y estadisticas...")
        loader.execute(INDEX_DDL)
        loader.execute(
            "ANALYZE ex05_products; "
            "ANALYZE ex05_inventory; "
            "ANALYZE ex05_customers; "
            "ANALYZE ex05_orders; "
            "ANALYZE ex05_order_items; "
            "ANALYZE ex05_order_attempts;"
        )
        loader.conn.commit()

        customer_count = loader.table_count("ex05_customers")

    print(f"[ex05] Listo: {customer_count:,} clientes")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args()
    run(small=args.small, dsn=args.dsn)
