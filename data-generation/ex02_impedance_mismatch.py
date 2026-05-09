"""
Seed — Ejercicio 02: Impedance Mismatch

Genera un modelo de pedidos deliberadamente normalizado:
  - customers
  - products
  - orders
  - order_lines
  - order_addresses
  - payments
  - shipments
  - tracking_events

El objetivo del ejercicio es reconstruir un agregado Order realista desde 6+
relaciones y observar el coste conceptual y físico del mapping objeto-relacional.
"""

import datetime
import os
import sys

import numpy as np
from faker import Faker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.pg_loader import DEFAULT_DSN, PGLoader

SEED = 43
rng = np.random.default_rng(SEED)
fake = Faker("es_ES")
fake.seed_instance(SEED)

FULL_CUSTOMERS = 120_000
FULL_PRODUCTS = 8_000
FULL_ORDERS = 500_000

SMALL_CUSTOMERS = 20_000
SMALL_PRODUCTS = 1_500
SMALL_ORDERS = 60_000

STATUSES = ["created", "paid", "packed", "shipped", "delivered", "cancelled"]
STATUS_WEIGHTS = [0.05, 0.10, 0.12, 0.18, 0.50, 0.05]
PAYMENT_METHODS = ["card", "paypal", "bank_transfer", "bizum"]
TRACKING_EVENTS = ["created", "paid", "packed", "shipped", "in_transit", "out_for_delivery", "delivered"]
CITIES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Zaragoza", "Malaga", "Alicante"]
CATEGORIES = ["electronica", "hogar", "moda", "deporte", "libros", "juguetes", "alimentacion"]

DDL = """
DROP TABLE IF EXISTS ex02_tracking_events CASCADE;
DROP TABLE IF EXISTS ex02_shipments CASCADE;
DROP TABLE IF EXISTS ex02_payments CASCADE;
DROP TABLE IF EXISTS ex02_order_addresses CASCADE;
DROP TABLE IF EXISTS ex02_order_lines CASCADE;
DROP TABLE IF EXISTS ex02_orders CASCADE;
DROP TABLE IF EXISTS ex02_products CASCADE;
DROP TABLE IF EXISTS ex02_customers CASCADE;

CREATE TABLE ex02_customers (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    full_name   TEXT NOT NULL,
    segment     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE ex02_products (
    id          BIGSERIAL PRIMARY KEY,
    sku         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    list_price  NUMERIC(10,2) NOT NULL
);

CREATE TABLE ex02_orders (
    id           BIGSERIAL PRIMARY KEY,
    customer_id  BIGINT NOT NULL REFERENCES ex02_customers(id),
    order_number TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL,
    placed_at    TIMESTAMPTZ NOT NULL,
    currency     CHAR(3) NOT NULL DEFAULT 'EUR'
);

CREATE TABLE ex02_order_lines (
    id          BIGSERIAL PRIMARY KEY,
    order_id    BIGINT NOT NULL REFERENCES ex02_orders(id),
    product_id  BIGINT NOT NULL REFERENCES ex02_products(id),
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) NOT NULL,
    discount    NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE ex02_order_addresses (
    id            BIGSERIAL PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES ex02_orders(id),
    address_type  TEXT NOT NULL CHECK (address_type IN ('billing', 'shipping')),
    street        TEXT NOT NULL,
    city          TEXT NOT NULL,
    postal_code   TEXT NOT NULL,
    country       TEXT NOT NULL DEFAULT 'ES'
);

CREATE TABLE ex02_payments (
    id              BIGSERIAL PRIMARY KEY,
    order_id         BIGINT NOT NULL REFERENCES ex02_orders(id),
    method           TEXT NOT NULL,
    amount           NUMERIC(10,2) NOT NULL,
    authorized_at    TIMESTAMPTZ,
    captured_at      TIMESTAMPTZ,
    payment_status   TEXT NOT NULL
);

CREATE TABLE ex02_shipments (
    id              BIGSERIAL PRIMARY KEY,
    order_id         BIGINT NOT NULL REFERENCES ex02_orders(id),
    carrier          TEXT NOT NULL,
    tracking_number  TEXT NOT NULL,
    shipped_at       TIMESTAMPTZ,
    delivered_at     TIMESTAMPTZ
);

CREATE TABLE ex02_tracking_events (
    id           BIGSERIAL PRIMARY KEY,
    shipment_id  BIGINT NOT NULL REFERENCES ex02_shipments(id),
    event_type   TEXT NOT NULL,
    event_at     TIMESTAMPTZ NOT NULL,
    location     TEXT NOT NULL
);
"""

INDEX_DDL = """
CREATE INDEX idx_ex02_orders_customer ON ex02_orders(customer_id);
CREATE INDEX idx_ex02_orders_placed ON ex02_orders(placed_at DESC);
CREATE INDEX idx_ex02_lines_order ON ex02_order_lines(order_id);
CREATE INDEX idx_ex02_lines_product ON ex02_order_lines(product_id);
CREATE INDEX idx_ex02_addr_order_type ON ex02_order_addresses(order_id, address_type);
CREATE INDEX idx_ex02_payments_order ON ex02_payments(order_id);
CREATE INDEX idx_ex02_shipments_order ON ex02_shipments(order_id);
CREATE INDEX idx_ex02_tracking_shipment ON ex02_tracking_events(shipment_id, event_at);
"""


def _customers(n: int):
    start = datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc)
    for i in range(n):
        yield (
            f"cliente.{i}@{fake.free_email_domain()}",
            fake.name(),
            rng.choice(["consumer", "business", "vip"], p=[0.78, 0.17, 0.05]),
            (start + datetime.timedelta(days=int(rng.integers(0, 1200)))).isoformat(),
        )


def _products(n: int):
    for i in range(n):
        category = rng.choice(CATEGORIES)
        price = round(float(rng.lognormal(mean=3.4, sigma=0.55)), 2)
        yield (f"SKU-{i:07d}", f"{fake.word().capitalize()} {category}", category, price)


def _orders(n_orders: int, n_customers: int):
    start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    seconds = int((end - start).total_seconds())
    for i in range(n_orders):
        placed_at = start + datetime.timedelta(seconds=int(rng.integers(0, seconds)))
        yield (
            int(rng.integers(1, n_customers + 1)),
            f"MER-{2024 + (i % 2)}-{i:09d}",
            rng.choice(STATUSES, p=STATUS_WEIGHTS),
            placed_at.isoformat(),
            "EUR",
        )


def _addresses(order_ids: range):
    for order_id in order_ids:
        city = rng.choice(CITIES)
        postal = f"{int(rng.integers(1000, 52999)):05d}"
        street = fake.street_address().replace("\n", " ")
        yield (order_id, "billing", street, city, postal, "ES")
        if rng.random() < 0.72:
            yield (order_id, "shipping", street, city, postal, "ES")
        else:
            yield (
                order_id,
                "shipping",
                fake.street_address().replace("\n", " "),
                rng.choice(CITIES),
                f"{int(rng.integers(1000, 52999)):05d}",
                "ES",
            )


def _lines(n_orders: int, n_products: int, product_prices: list[float]):
    for order_id in range(1, n_orders + 1):
        n_lines = int(rng.integers(1, 6))
        products = rng.choice(np.arange(1, n_products + 1), size=n_lines, replace=False)
        for product_id in products:
            qty = int(rng.integers(1, 4))
            unit_price = product_prices[int(product_id) - 1]
            discount = round(unit_price * float(rng.choice([0, 0, 0.05, 0.10, 0.15])), 2)
            yield (order_id, int(product_id), qty, unit_price, discount)


def _payments(order_totals: list[float]):
    for order_id, total in enumerate(order_totals, start=1):
        authorized_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(
            seconds=int(rng.integers(0, 63_000_000))
        )
        captured_at = authorized_at + datetime.timedelta(minutes=int(rng.integers(1, 180)))
        status = rng.choice(["authorized", "captured", "refunded", "failed"], p=[0.10, 0.80, 0.04, 0.06])
        yield (
            order_id,
            rng.choice(PAYMENT_METHODS),
            round(total, 2),
            authorized_at.isoformat(),
            captured_at.isoformat() if status in ("captured", "refunded") else None,
            status,
        )


def _shipments(order_ids: range):
    for order_id in order_ids:
        shipped_at = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc) + datetime.timedelta(
            seconds=int(rng.integers(0, 63_000_000))
        )
        delivered_at = shipped_at + datetime.timedelta(days=int(rng.integers(1, 7)))
        yield (
            order_id,
            rng.choice(["Correos", "SEUR", "DHL", "MRW"]),
            f"TRK{order_id:010d}",
            shipped_at.isoformat(),
            delivered_at.isoformat(),
        )


def _tracking_events(n_orders: int):
    for shipment_id in range(1, n_orders + 1):
        base = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc) + datetime.timedelta(
            seconds=int(rng.integers(0, 63_000_000))
        )
        n_events = int(rng.integers(3, 7))
        for pos, event in enumerate(TRACKING_EVENTS[:n_events]):
            yield (
                shipment_id,
                event,
                (base + datetime.timedelta(hours=pos * int(rng.integers(6, 30)))).isoformat(),
                rng.choice(CITIES),
            )


def run(small: bool = False, dsn: str = DEFAULT_DSN):
    n_customers = SMALL_CUSTOMERS if small else FULL_CUSTOMERS
    n_products = SMALL_PRODUCTS if small else FULL_PRODUCTS
    n_orders = SMALL_ORDERS if small else FULL_ORDERS
    mode = "SMALL" if small else "FULL"
    print(f"[ex02] Modo {mode}: {n_orders:,} pedidos normalizados")

    with PGLoader(dsn) as loader:
        print("[ex02] Creando esquema...")
        loader.execute(DDL)
        loader.conn.commit()

        print(f"[ex02] Insertando {n_customers:,} clientes...")
        loader.copy_csv_chunked("ex02_customers", _customers(n_customers), ["email", "full_name", "segment", "created_at"], 50_000, n_customers, "customers")

        print(f"[ex02] Insertando {n_products:,} productos...")
        product_rows = list(_products(n_products))
        product_prices = [float(row[3]) for row in product_rows]
        loader.copy_csv("ex02_products", product_rows, ["sku", "name", "category", "list_price"])
        loader.conn.commit()

        print(f"[ex02] Insertando {n_orders:,} pedidos...")
        loader.copy_csv_chunked("ex02_orders", _orders(n_orders, n_customers), ["customer_id", "order_number", "status", "placed_at", "currency"], 50_000, n_orders, "orders")

        print("[ex02] Insertando direcciones...")
        loader.copy_csv_chunked("ex02_order_addresses", _addresses(range(1, n_orders + 1)), ["order_id", "address_type", "street", "city", "postal_code", "country"], 100_000, n_orders * 2, "addresses")

        print("[ex02] Insertando lineas de pedido...")
        line_totals = [0.0] * n_orders

        def line_generator():
            for order_id, product_id, qty, unit_price, discount in _lines(n_orders, n_products, product_prices):
                line_totals[order_id - 1] += qty * (unit_price - discount)
                yield (order_id, product_id, qty, unit_price, discount)

        loader.copy_csv_chunked("ex02_order_lines", line_generator(), ["order_id", "product_id", "quantity", "unit_price", "discount"], 100_000, n_orders * 3, "lines")

        print("[ex02] Insertando pagos...")
        loader.copy_csv_chunked("ex02_payments", _payments(line_totals), ["order_id", "method", "amount", "authorized_at", "captured_at", "payment_status"], 50_000, n_orders, "payments")

        print("[ex02] Insertando envios...")
        loader.copy_csv_chunked("ex02_shipments", _shipments(range(1, n_orders + 1)), ["order_id", "carrier", "tracking_number", "shipped_at", "delivered_at"], 50_000, n_orders, "shipments")

        print("[ex02] Insertando eventos de tracking...")
        loader.copy_csv_chunked("ex02_tracking_events", _tracking_events(n_orders), ["shipment_id", "event_type", "event_at", "location"], 100_000, n_orders * 4, "tracking")

        print("[ex02] Creando indices y analizando...")
        loader.execute(INDEX_DDL)
        loader.execute("ANALYZE ex02_customers; ANALYZE ex02_products; ANALYZE ex02_orders; ANALYZE ex02_order_lines; ANALYZE ex02_order_addresses; ANALYZE ex02_payments; ANALYZE ex02_shipments; ANALYZE ex02_tracking_events;")
        loader.conn.commit()

        orders_count = loader.table_count("ex02_orders")
        lines_count = loader.table_count("ex02_order_lines")
        tracking_count = loader.table_count("ex02_tracking_events")

    print(f"[ex02] Listo: {orders_count:,} pedidos, {lines_count:,} lineas, {tracking_count:,} eventos")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args()
    run(small=args.small, dsn=args.dsn)
