"""
Seed — Ejercicio 01: Schema Rigidity y EAV

Genera:
  - Tabla `ex01_users`: 10M filas (1M en modo --small)
    con perfil evolutivo: B2C (60%), B2B (30%), Freelancer (10%)
  - Tabla `ex01_user_attributes`: patrón EAV sobre los mismos usuarios
    (~3 atributos por usuario en media → ~30M filas / 3M en small)

El objetivo del ejercicio es:
  1. Medir el coste de ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT 'x'
     en una tabla de 10M filas y observar el lock exclusivo de esquema
  2. Demostrar el efecto convoy de bloqueos cuando llega un ALTER con tráfico activo
  3. Experimentar el anti-patrón EAV y su impacto en el planner vs esquema normalizado

Tiempo estimado: ~3 min (full) / ~30 s (small)
"""

import os
import sys
import random
import datetime

import numpy as np
from faker import Faker

# Añade el directorio padre al path para importar utils
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.pg_loader import PGLoader, DEFAULT_DSN

SEED = 42
rng = np.random.default_rng(SEED)
fake = Faker("es_ES")
fake.seed_instance(SEED)

FULL_USERS   = 10_000_000
SMALL_USERS  =  1_000_000

USER_TYPES = ["b2c", "b2b", "freelancer"]
USER_TYPE_WEIGHTS = [0.60, 0.30, 0.10]

# Atributos posibles por tipo de usuario
ATTRIBUTES = {
    "b2c":        ["newsletter", "loyalty_tier", "preferred_language", "birth_year"],
    "b2b":        ["company_name", "tax_id", "industry", "employees_range", "account_manager"],
    "freelancer": ["portfolio_url", "skills", "hourly_rate", "availability"],
}

INDUSTRIES = [
    "Tecnología", "Retail", "Banca", "Manufactura", "Logística",
    "Salud", "Energía", "Consultoría", "Turismo", "Automoción",
    "Alimentación", "Construcción", "Medios", "Seguros",
]

SKILLS = [
    "Python", "SQL", "Java", "React", "Machine Learning",
    "DevOps", "Tableau", "Spark", "Kotlin", "Go",
    "Data Engineering", "Cloud (AWS)", "Cloud (GCP)", "Ciberseguridad",
]

AVAILABILITY = ["inmediata", "2 semanas", "1 mes", "3 meses"]

DDL = """
-- Ejercicio 01: Schema Rigidity
-- Tabla de usuarios en su versión inicial (solo columnas básicas, como en un B2C original)
DROP TABLE IF EXISTS ex01_user_attributes CASCADE;
DROP TABLE IF EXISTS ex01_users CASCADE;

CREATE TABLE ex01_users (
    id           BIGSERIAL PRIMARY KEY,
    email        TEXT        NOT NULL UNIQUE,
    first_name   TEXT        NOT NULL,
    last_name    TEXT        NOT NULL,
    user_type    TEXT        NOT NULL CHECK (user_type IN ('b2c', 'b2b', 'freelancer')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active    BOOLEAN     NOT NULL DEFAULT true
    -- Nota: las columnas específicas de B2B/Freelancer NO están aquí todavía.
    -- El ejercicio consiste en añadirlas después de poblar la tabla.
);

-- Tabla EAV: almacena atributos arbitrarios de cada usuario como filas clave-valor
-- Este es el anti-patrón que se analiza en el paso 4 del ejercicio
CREATE TABLE ex01_user_attributes (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT      NOT NULL REFERENCES ex01_users(id),
    attr_name    TEXT        NOT NULL,
    attr_value   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

INDEX_DDL = """
-- Índices para el ejercicio (el alumno observará cuáles ayudan y cuáles no)
CREATE INDEX idx_ex01_users_type    ON ex01_users(user_type);
CREATE INDEX idx_ex01_users_created ON ex01_users(created_at);
CREATE INDEX idx_ex01_eav_user      ON ex01_user_attributes(user_id);
CREATE INDEX idx_ex01_eav_name      ON ex01_user_attributes(attr_name);
"""


def _user_generator(n: int):
    """Genera n filas de usuarios como tuplas (email, first_name, last_name, user_type, created_at, is_active)."""
    types = rng.choice(USER_TYPES, size=n, p=USER_TYPE_WEIGHTS)
    # Distribución de created_at: uniforme en los últimos 3 años
    start_ts = datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc)
    end_ts   = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    range_seconds = int((end_ts - start_ts).total_seconds())
    offsets = rng.integers(0, range_seconds, size=n)
    is_active = rng.choice([True, False], size=n, p=[0.85, 0.15])

    used_emails = set()
    for i in range(n):
        # Email único: nombre + número aleatorio para evitar colisiones
        base = fake.email().split("@")
        email = f"{base[0]}.{i}@{base[1]}"
        created_at = start_ts + datetime.timedelta(seconds=int(offsets[i]))
        yield (
            email,
            fake.first_name(),
            fake.last_name(),
            types[i],
            created_at.isoformat(),
            bool(is_active[i]),
        )


def _eav_generator(user_ids: list[int], user_types: list[str]):
    """Genera filas EAV: ~3 atributos por usuario en media, con varianza."""
    for uid, utype in zip(user_ids, user_types):
        attrs = ATTRIBUTES[utype]
        n_attrs = max(1, int(rng.poisson(lam=3)))
        chosen = rng.choice(attrs, size=min(n_attrs, len(attrs)), replace=False)
        for attr in chosen:
            if attr == "birth_year":
                val = str(rng.integers(1950, 2005))
            elif attr == "hourly_rate":
                val = str(round(float(rng.uniform(20, 150)), 2))
            elif attr == "employees_range":
                val = rng.choice(["1-10", "11-50", "51-200", "201-1000", "1000+"])
            elif attr == "loyalty_tier":
                val = rng.choice(["bronze", "silver", "gold", "platinum"])
            elif attr == "preferred_language":
                val = rng.choice(["es", "en", "fr", "de", "pt"])
            elif attr == "newsletter":
                val = rng.choice(["true", "false"])
            elif attr == "company_name":
                val = fake.company()
            elif attr == "tax_id":
                val = f"B{rng.integers(10_000_000, 99_999_999):08d}"
            elif attr == "industry":
                val = rng.choice(INDUSTRIES)
            elif attr == "account_manager":
                val = fake.name()
            elif attr == "portfolio_url":
                val = f"https://portfolio.{fake.domain_name()}"
            elif attr == "skills":
                val = rng.choice(SKILLS)
            elif attr == "availability":
                val = rng.choice(AVAILABILITY)
            else:
                val = fake.word()
            yield (uid, attr, val, datetime.datetime.now(datetime.timezone.utc).isoformat())


def run(small: bool = False, dsn: str = DEFAULT_DSN):
    n_users = SMALL_USERS if small else FULL_USERS
    mode = "SMALL" if small else "FULL"
    print(f"[ex01] Modo {mode}: generando {n_users:,} usuarios + tabla EAV")

    with PGLoader(dsn) as loader:
        print("[ex01] Creando esquema...")
        loader.execute(DDL)
        loader.conn.commit()

        print(f"[ex01] Insertando {n_users:,} usuarios via COPY...")
        loaded = loader.copy_csv_chunked(
            table="ex01_users",
            generator=_user_generator(n_users),
            columns=["email", "first_name", "last_name", "user_type", "created_at", "is_active"],
            chunk_size=50_000,
            total=n_users,
            label="users",
        )

        # Recuperamos user_ids y tipos para generar el EAV de forma consistente
        print("[ex01] Leyendo IDs de usuarios para generar EAV...")
        with loader.conn.cursor() as cur:
            cur.execute("SELECT id, user_type FROM ex01_users ORDER BY id")
            rows = cur.fetchall()
        user_ids   = [r[0] for r in rows]
        user_types = [r[1] for r in rows]

        print(f"[ex01] Generando atributos EAV (~{len(user_ids)*3:,} filas estimadas)...")
        loader.copy_csv_chunked(
            table="ex01_user_attributes",
            generator=_eav_generator(user_ids, user_types),
            columns=["user_id", "attr_name", "attr_value", "created_at"],
            chunk_size=100_000,
            total=len(user_ids) * 3,
            label="eav",
        )

        print("[ex01] Creando índices...")
        loader.execute(INDEX_DDL)
        loader.conn.commit()

        users_count = loader.table_count("ex01_users")
        eav_count   = loader.table_count("ex01_user_attributes")

    print(f"[ex01] Listo: {users_count:,} usuarios, {eav_count:,} atributos EAV")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--dsn",   default=DEFAULT_DSN)
    args = parser.parse_args()
    run(small=args.small, dsn=args.dsn)
