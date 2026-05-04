"""
Utilidades compartidas para cargar datos en PostgreSQL usando el protocolo COPY.
Uso: from utils.pg_loader import PGLoader
"""

import io
import time
import psycopg2
from contextlib import contextmanager

# Configuración de conexión por defecto (sobreescribible con variables de entorno)
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/clase01"


class PGLoader:
    """Cargador masivo de datos usando COPY — entre 10x y 100x más rápido que INSERT."""

    def __init__(self, dsn: str = DEFAULT_DSN):
        self.dsn = dsn
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.close()

    def execute(self, sql: str, params=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def executemany(self, sql: str, values):
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)

    def copy_csv(self, table: str, rows: list[tuple], columns: list[str] | None = None):
        """
        Carga filas en la tabla usando COPY FROM STDIN CSV.
        rows: lista de tuplas con los valores (en el mismo orden que columns)
        columns: lista de nombres de columna (opcional)
        """
        buf = io.StringIO()
        for row in rows:
            # Escapar valores para CSV: None → \N, strings con comillas dobles
            csv_row = []
            for val in row:
                if val is None:
                    csv_row.append("\\N")
                else:
                    s = str(val).replace('"', '""')
                    if "," in s or "\n" in s or '"' in s:
                        csv_row.append(f'"{s}"')
                    else:
                        csv_row.append(s)
            buf.write(",".join(csv_row) + "\n")
        buf.seek(0)

        col_clause = f"({', '.join(columns)})" if columns else ""
        sql = f"COPY {table} {col_clause} FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
        with self.conn.cursor() as cur:
            cur.copy_expert(sql, buf)

    def copy_csv_chunked(
        self,
        table: str,
        generator,
        columns: list[str] | None = None,
        chunk_size: int = 50_000,
        total: int | None = None,
        label: str = "",
    ):
        """
        Carga datos desde un generador en chunks para no saturar la RAM.
        generator: iterable de tuplas
        total: número total esperado (para mostrar progreso)
        """
        start = time.time()
        loaded = 0
        chunk = []

        for row in generator:
            chunk.append(row)
            if len(chunk) >= chunk_size:
                self.copy_csv(table, chunk, columns)
                self.conn.commit()
                loaded += len(chunk)
                chunk = []
                elapsed = time.time() - start
                rate = loaded / elapsed if elapsed > 0 else 0
                pct = f"{loaded/total*100:.1f}%" if total else f"{loaded:,} rows"
                print(f"  [COPY] {label} {pct} — {rate:,.0f} rows/s", end="\r", flush=True)

        if chunk:
            self.copy_csv(table, chunk, columns)
            self.conn.commit()
            loaded += len(chunk)

        elapsed = time.time() - start
        print(f"  [COPY] {label} {loaded:,} filas en {elapsed:.1f}s ({loaded/elapsed:,.0f} rows/s)")
        return loaded

    @contextmanager
    def transaction(self):
        try:
            yield self
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def table_count(self, table: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]
