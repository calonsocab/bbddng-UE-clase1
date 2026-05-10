"""
Seed — Ejercicio 04: hot reads y latencia en PostgreSQL.

Genera un caso operacional de ficha de producto:
  - una lectura normalizada recalcula metricas recientes desde eventos,
  - una proyeccion preparada lee el mismo resumen desde una tabla derivada.

El dataset usa una distribucion sesgada: pocos productos reciben muchas lecturas y
eventos. Esto permite que la latencia sea visible en el modo full sin introducir
Redis ni otro motor.
"""

import datetime
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.pg_loader import DEFAULT_DSN, PGLoader

SEED = 46
rng = np.random.default_rng(SEED)

N_PRODUCTS = 60_000
SMALL_EVENTS = 300_000
FULL_EVENTS = 2_000_000

CATEGORIES = ["electronica", "hogar", "moda", "deporte", "libros", "juguetes", "alimentacion", "salud"]
BRANDS = [f"brand_{i:03d}" for i in range(1, 181)]
EVENT_TYPES = ["view", "cart", "purchase"]
EVENT_PROBS = [0.86, 0.10, 0.04]

DDL = """
DROP TABLE IF EXISTS ex04_product_summary CASCADE;
DROP TABLE IF EXISTS ex04_product_events CASCADE;
DROP TABLE IF EXISTS ex04_reviews CASCADE;
DROP TABLE IF EXISTS ex04_inventory CASCADE;
DROP TABLE IF EXISTS ex04_products CASCADE;

CREATE TABLE ex04_products (
    id BIGINT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    name TEXT NOT NULL,
    base_price NUMERIC(10,2) NOT NULL,
    active BOOLEAN NOT NULL,
    popularity_rank INTEGER NOT NULL
);

CREATE TABLE ex04_inventory (
    product_id BIGINT PRIMARY KEY REFERENCES ex04_products(id),
    units_available INTEGER NOT NULL,
    warehouse_count INTEGER NOT NULL,
    last_restocked DATE NOT NULL
);

CREATE TABLE ex04_reviews (
    product_id BIGINT PRIMARY KEY REFERENCES ex04_products(id),
    review_count INTEGER NOT NULL,
    avg_rating NUMERIC(3,2) NOT NULL
);

CREATE TABLE ex04_product_events (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES ex04_products(id),
    event_type TEXT NOT NULL,
    event_ts TIMESTAMP NOT NULL
);
"""

INDEX_DDL = """
CREATE INDEX idx_ex04_products_category ON ex04_products(category);
CREATE INDEX idx_ex04_products_rank ON ex04_products(popularity_rank);
CREATE INDEX idx_ex04_events_product_ts ON ex04_product_events(product_id, event_ts DESC);
CREATE INDEX idx_ex04_events_ts ON ex04_product_events(event_ts);
"""

SUMMARY_DDL = """
DROP TABLE IF EXISTS ex04_product_summary;

CREATE TABLE ex04_product_summary AS
WITH recent AS (
    SELECT
        product_id,
        COUNT(*) FILTER (WHERE event_type = 'view') AS views_7d,
        COUNT(*) FILTER (WHERE event_type = 'cart') AS carts_7d,
        COUNT(*) FILTER (WHERE event_type = 'purchase') AS purchases_7d
    FROM ex04_product_events
    WHERE event_ts >= TIMESTAMP '2026-05-09 00:00:00' - INTERVAL '7 days'
    GROUP BY product_id
)
SELECT
    p.id AS product_id,
    p.sku,
    p.category,
    p.brand,
    p.name,
    p.base_price,
    i.units_available,
    i.warehouse_count,
    r.review_count,
    r.avg_rating,
    COALESCE(recent.views_7d, 0) AS views_7d,
    COALESCE(recent.carts_7d, 0) AS carts_7d,
    COALESCE(recent.purchases_7d, 0) AS purchases_7d,
    (
        COALESCE(recent.views_7d, 0) * 0.01
        + COALESCE(recent.carts_7d, 0) * 0.20
        + COALESCE(recent.purchases_7d, 0) * 1.50
        + r.avg_rating * 5
    )::NUMERIC(12,2) AS hot_score,
    TIMESTAMP '2026-05-09 00:00:00' AS refreshed_at
FROM ex04_products p
JOIN ex04_inventory i ON i.product_id = p.id
JOIN ex04_reviews r ON r.product_id = p.id
LEFT JOIN recent ON recent.product_id = p.id;

ALTER TABLE ex04_product_summary ADD PRIMARY KEY (product_id);
CREATE INDEX idx_ex04_summary_hot_score ON ex04_product_summary(hot_score DESC);
ANALYZE ex04_product_summary;
"""


def _product_weights(n: int):
    ranks = np.arange(1, n + 1, dtype=np.float64)
    weights = 1 / np.power(ranks, 1.15)
    return weights / weights.sum()


def _products(n: int):
    for product_id in range(1, n + 1):
        category = rng.choice(CATEGORIES, p=[0.22, 0.14, 0.14, 0.12, 0.10, 0.10, 0.10, 0.08])
        brand = rng.choice(BRANDS)
        price = round(float(rng.lognormal(mean=3.4, sigma=0.75)), 2)
        active = rng.random() > 0.03
        yield (
            product_id,
            f"EX04-SKU-{product_id:07d}",
            category,
            brand,
            f"{category}-{brand}-modelo-{product_id:07d}",
            price,
            active,
            product_id,
        )


def _inventory(n: int):
    base = datetime.date(2026, 5, 9)
    for product_id in range(1, n + 1):
        hotness = max(1, int(8000 / np.sqrt(product_id)))
        units = int(rng.integers(0, hotness + 80))
        warehouses = int(rng.integers(1, 9))
        restocked = base - datetime.timedelta(days=int(rng.integers(0, 45)))
        yield (product_id, units, warehouses, restocked.isoformat())


def _reviews(n: int):
    for product_id in range(1, n + 1):
        review_count = int(max(0, rng.poisson(lam=max(3, 650 / np.sqrt(product_id)))))
        avg_rating = round(float(np.clip(rng.normal(loc=4.05, scale=0.42), 1.0, 5.0)), 2)
        yield (product_id, review_count, avg_rating)


def _events(n_events: int, n_products: int):
    weights = _product_weights(n_products)
    base = datetime.datetime(2026, 5, 9, 0, 0, 0)
    chunk_size = 100_000
    remaining = n_events

    while remaining > 0:
        size = min(chunk_size, remaining)
        product_ids = rng.choice(np.arange(1, n_products + 1), size=size, p=weights)
        event_types = rng.choice(EVENT_TYPES, size=size, p=EVENT_PROBS)
        minutes_back = rng.integers(0, 60 * 24 * 60, size=size)
        for product_id, event_type, minute_back in zip(product_ids, event_types, minutes_back):
            event_ts = base - datetime.timedelta(minutes=int(minute_back))
            yield (int(product_id), str(event_type), event_ts.isoformat(sep=" "))
        remaining -= size


def run(small: bool = False, dsn: str = DEFAULT_DSN):
    n_events = SMALL_EVENTS if small else FULL_EVENTS
    mode = "SMALL" if small else "FULL"
    print(f"[ex04] Modo {mode}: {N_PRODUCTS:,} productos, {n_events:,} eventos de lectura")

    with PGLoader(dsn) as loader:
        print("[ex04] Creando esquema...")
        loader.execute(DDL)
        loader.conn.commit()

        print("[ex04] Insertando productos, inventario y reviews...")
        loader.copy_csv_chunked(
            "ex04_products",
            _products(N_PRODUCTS),
            ["id", "sku", "category", "brand", "name", "base_price", "active", "popularity_rank"],
            50_000,
            N_PRODUCTS,
            "products",
        )
        loader.copy_csv_chunked(
            "ex04_inventory",
            _inventory(N_PRODUCTS),
            ["product_id", "units_available", "warehouse_count", "last_restocked"],
            50_000,
            N_PRODUCTS,
            "inventory",
        )
        loader.copy_csv_chunked(
            "ex04_reviews",
            _reviews(N_PRODUCTS),
            ["product_id", "review_count", "avg_rating"],
            50_000,
            N_PRODUCTS,
            "reviews",
        )

        print(f"[ex04] Insertando {n_events:,} eventos...")
        loader.copy_csv_chunked(
            "ex04_product_events",
            _events(n_events, N_PRODUCTS),
            ["product_id", "event_type", "event_ts"],
            100_000,
            n_events,
            "events",
        )

        print("[ex04] Creando indices...")
        loader.execute(INDEX_DDL)
        loader.execute("ANALYZE ex04_products; ANALYZE ex04_inventory; ANALYZE ex04_reviews; ANALYZE ex04_product_events;")
        loader.conn.commit()

        print("[ex04] Creando proyeccion de lectura...")
        loader.execute(SUMMARY_DDL)
        loader.conn.commit()

        product_count = loader.table_count("ex04_products")
        event_count = loader.table_count("ex04_product_events")

    print(f"[ex04] Listo: {product_count:,} productos y {event_count:,} eventos")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args()
    run(small=args.small, dsn=args.dsn)
