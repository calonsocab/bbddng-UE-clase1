"""
Seed — Ejercicio 03: reporting y preagregacion para ventas.

Genera un esquema tipo estrella en PostgreSQL:
  - ex03_sales fact table
  - ex03_customers, ex03_products, ex03_stores, ex03_dates, ex03_promotions

El dataset reducido busca ser ejecutable en portatil. El dataset completo aumenta
la tabla de hechos, pero no intenta forzar decenas de millones de filas por defecto
porque romperia el requisito transversal de ejecucion razonable en clase.
"""

import datetime
import os
import sys

import numpy as np
from faker import Faker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.pg_loader import DEFAULT_DSN, PGLoader

SEED = 44
rng = np.random.default_rng(SEED)
fake = Faker("es_ES")
fake.seed_instance(SEED)

SMALL_SALES = 500_000
FULL_SALES = 5_000_000

N_CUSTOMERS = 120_000
N_PRODUCTS = 12_000
N_STORES = 250
N_PROMOTIONS = 80

REGIONS = ["Norte", "Sur", "Este", "Oeste", "Centro", "Online"]
SEGMENTS = ["consumer", "business", "vip"]
CATEGORIES = ["electronica", "hogar", "moda", "deporte", "libros", "juguetes", "alimentacion", "salud"]
CHANNELS = ["web", "mobile", "store", "marketplace"]

DDL = """
DROP MATERIALIZED VIEW IF EXISTS ex03_category_product_report_mv;
DROP MATERIALIZED VIEW IF EXISTS ex03_category_product_read_mv;
DROP TABLE IF EXISTS ex03_sales CASCADE;
DROP TABLE IF EXISTS ex03_customers CASCADE;
DROP TABLE IF EXISTS ex03_products CASCADE;
DROP TABLE IF EXISTS ex03_stores CASCADE;
DROP TABLE IF EXISTS ex03_dates CASCADE;
DROP TABLE IF EXISTS ex03_promotions CASCADE;

CREATE TABLE ex03_customers (
    id BIGSERIAL PRIMARY KEY,
    segment TEXT NOT NULL,
    region TEXT NOT NULL,
    signup_date DATE NOT NULL
);

CREATE TABLE ex03_products (
    id BIGSERIAL PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    base_price NUMERIC(10,2) NOT NULL
);

CREATE TABLE ex03_stores (
    id BIGSERIAL PRIMARY KEY,
    region TEXT NOT NULL,
    city TEXT NOT NULL,
    channel TEXT NOT NULL
);

CREATE TABLE ex03_promotions (
    id BIGSERIAL PRIMARY KEY,
    campaign_name TEXT NOT NULL,
    discount_pct NUMERIC(5,2) NOT NULL,
    channel TEXT NOT NULL
);

CREATE TABLE ex03_dates (
    id INTEGER PRIMARY KEY,
    day DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    week INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE ex03_sales (
    id BIGSERIAL PRIMARY KEY,
    date_id INTEGER NOT NULL REFERENCES ex03_dates(id),
    customer_id BIGINT NOT NULL REFERENCES ex03_customers(id),
    product_id BIGINT NOT NULL REFERENCES ex03_products(id),
    store_id BIGINT NOT NULL REFERENCES ex03_stores(id),
    promotion_id BIGINT REFERENCES ex03_promotions(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL,
    gross_amount NUMERIC(12,2) NOT NULL,
    net_amount NUMERIC(12,2) NOT NULL
);
"""

INDEX_DDL = """
CREATE INDEX idx_ex03_sales_date ON ex03_sales(date_id);
CREATE INDEX idx_ex03_sales_product ON ex03_sales(product_id);
CREATE INDEX idx_ex03_sales_customer ON ex03_sales(customer_id);
CREATE INDEX idx_ex03_sales_store ON ex03_sales(store_id);
CREATE INDEX idx_ex03_sales_promo ON ex03_sales(promotion_id);
CREATE INDEX idx_ex03_products_category ON ex03_products(category);
CREATE INDEX idx_ex03_customers_segment_region ON ex03_customers(segment, region);
CREATE INDEX idx_ex03_dates_year_month ON ex03_dates(year, month);
"""


def _dates():
    start = datetime.date(2024, 1, 1)
    for i in range(730):
        day = start + datetime.timedelta(days=i)
        yield (i + 1, day.isoformat(), day.year, day.month, int(day.strftime("%V")), day.weekday() >= 5)


def _customers(n):
    start = datetime.date(2020, 1, 1)
    for _ in range(n):
        yield (
            rng.choice(SEGMENTS, p=[0.78, 0.17, 0.05]),
            rng.choice(REGIONS, p=[0.16, 0.15, 0.17, 0.14, 0.18, 0.20]),
            (start + datetime.timedelta(days=int(rng.integers(0, 1700)))).isoformat(),
        )


def _products(n):
    for i in range(n):
        category = rng.choice(CATEGORIES, p=[0.18, 0.14, 0.16, 0.12, 0.10, 0.10, 0.12, 0.08])
        brand = f"brand_{int(rng.integers(1, 80)):02d}"
        price = round(float(rng.lognormal(mean=3.35, sigma=0.7)), 2)
        yield (f"EX03-SKU-{i:06d}", category, brand, price)


def _stores(n):
    for _ in range(n):
        channel = rng.choice(CHANNELS, p=[0.25, 0.25, 0.35, 0.15])
        region = "Online" if channel in ("web", "mobile", "marketplace") else rng.choice(REGIONS[:-1])
        yield (region, rng.choice(["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza", "Malaga"]), channel)


def _promotions(n):
    for i in range(n):
        yield (f"campaign_{i:03d}", round(float(rng.choice([5, 10, 15, 20, 25, 30])), 2), rng.choice(CHANNELS))


def _sales(n, product_prices):
    product_ids = np.arange(1, len(product_prices) + 1)
    # Zipf suave: pocos productos concentran muchas ventas, como en retail real.
    product_weights = 1 / np.sqrt(product_ids)
    product_weights = product_weights / product_weights.sum()
    for _ in range(n):
        product_id = int(rng.choice(product_ids, p=product_weights))
        qty = int(rng.integers(1, 5))
        unit_price = float(product_prices[product_id - 1])
        promo = int(rng.integers(1, N_PROMOTIONS + 1)) if rng.random() < 0.22 else None
        discount = 0.10 if promo else 0.0
        gross = round(unit_price * qty, 2)
        net = round(gross * (1 - discount), 2)
        yield (
            int(rng.integers(1, 731)),
            int(rng.integers(1, N_CUSTOMERS + 1)),
            product_id,
            int(rng.integers(1, N_STORES + 1)),
            promo,
            qty,
            unit_price,
            gross,
            net,
        )


def run(small: bool = False, dsn: str = DEFAULT_DSN):
    n_sales = SMALL_SALES if small else FULL_SALES
    mode = "SMALL" if small else "FULL"
    print(f"[ex03] Modo {mode}: {n_sales:,} ventas para reporting")

    with PGLoader(dsn) as loader:
        print("[ex03] Creando esquema...")
        loader.execute(DDL)
        loader.conn.commit()

        print("[ex03] Insertando dimensiones...")
        loader.copy_csv("ex03_dates", list(_dates()), ["id", "day", "year", "month", "week", "is_weekend"])
        loader.copy_csv_chunked("ex03_customers", _customers(N_CUSTOMERS), ["segment", "region", "signup_date"], 50_000, N_CUSTOMERS, "customers")
        product_rows = list(_products(N_PRODUCTS))
        product_prices = [float(row[3]) for row in product_rows]
        loader.copy_csv("ex03_products", product_rows, ["sku", "category", "brand", "base_price"])
        loader.copy_csv("ex03_stores", list(_stores(N_STORES)), ["region", "city", "channel"])
        loader.copy_csv("ex03_promotions", list(_promotions(N_PROMOTIONS)), ["campaign_name", "discount_pct", "channel"])
        loader.conn.commit()

        print(f"[ex03] Insertando {n_sales:,} ventas...")
        loader.copy_csv_chunked(
            "ex03_sales",
            _sales(n_sales, product_prices),
            ["date_id", "customer_id", "product_id", "store_id", "promotion_id", "quantity", "unit_price", "gross_amount", "net_amount"],
            100_000,
            n_sales,
            "sales",
        )

        print("[ex03] Creando indices y estadisticas...")
        loader.execute(INDEX_DDL)
        loader.execute("ANALYZE ex03_customers; ANALYZE ex03_products; ANALYZE ex03_stores; ANALYZE ex03_dates; ANALYZE ex03_promotions; ANALYZE ex03_sales;")
        loader.conn.commit()

        sales_count = loader.table_count("ex03_sales")

    print(f"[ex03] Listo: {sales_count:,} ventas")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args()
    run(small=args.small, dsn=args.dsn)
