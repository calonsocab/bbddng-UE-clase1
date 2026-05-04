-- Inicialización de la base de datos clase01
-- Se ejecuta una sola vez al crear el contenedor

-- Extensiones necesarias para los ejercicios
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- Usuario para la réplica de streaming
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'replicator') THEN
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replicator_pass';
  END IF;
END
$$;

-- Schema por defecto para la clase
-- Cada ejercicio creará sus propias tablas aquí o en schemas dedicados
COMMENT ON DATABASE clase01 IS 'Base de datos para clase01-intro: Bases de Datos de Nueva Generación';
