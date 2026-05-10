.PHONY: up up-admin down clean seed seed-fast psql replica-psql \
        lint-notebooks venv venv-clean _check-pg help

# ── Variables ────────────────────────────────────────────────────────────────
COMPOSE       = docker compose
PG_USER      ?= postgres
PG_DB        ?= clase01
PG_PORT      ?= 5432
REPLICA_PORT ?= 5433
DATA_GEN      = data-generation
VENV          = .venv

# Usa el Python del venv si existe; si no, el del sistema
PYTHON  := $(shell [ -x $(VENV)/bin/python ]  && echo $(VENV)/bin/python  || echo python3)
JUPYTER := $(shell [ -x $(VENV)/bin/jupyter ] && echo $(VENV)/bin/jupyter || echo jupyter)

# ── Entorno Python (venv) ────────────────────────────────────────────────────
venv:
	@echo "[+] Creando entorno virtual en $(VENV)/ ..."
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip --quiet
	$(VENV)/bin/pip install -r $(DATA_GEN)/requirements.txt
	@echo "[+] Listo. Usa 'source $(VENV)/bin/activate' para activarlo manualmente."
	@echo "    O simplemente usa 'make seed-fast', 'make exercise-01', etc. — ya apuntan al venv."

venv-clean:
	rm -rf $(VENV)
	@echo "[+] Venv eliminado."

# ── Infraestructura ──────────────────────────────────────────────────────────
up:
	@echo "[+] Levantando PostgreSQL 16 (primaria + réplica)..."
	$(COMPOSE) up -d postgres postgres-replica
	@echo "[+] Esperando healthchecks..."
	@until docker inspect clase01-postgres --format='{{.State.Health.Status}}' 2>/dev/null | grep -q healthy; do \
		printf '.'; sleep 2; done; echo " primaria OK"
	@until docker inspect clase01-replica --format='{{.State.Health.Status}}' 2>/dev/null | grep -q healthy; do \
		printf '.'; sleep 2; done; echo " réplica OK"

up-admin: up
	$(COMPOSE) --profile admin up -d pgadmin
	@echo "[+] pgAdmin disponible en http://localhost:$${PGADMIN_PORT:-8080}"

down:
	$(COMPOSE) down

clean:
	@echo "[!] Esto borrará todos los datos de los volúmenes de Docker."
	@read -p "¿Confirmas? [s/N] " confirm && [ "$$confirm" = "s" ] || exit 1
	$(COMPOSE) down -v
	@echo "[+] Volúmenes eliminados."

# ── Seeds ────────────────────────────────────────────────────────────────────
_check-pg:
	@docker exec clase01-postgres pg_isready -U postgres -d clase01 -q 2>/dev/null || \
		{ echo "[!] PostgreSQL no está disponible. Ejecuta 'make up' primero."; exit 1; }

seed: _check-pg
	@echo "[+] Generando datasets completos (puede tardar 30+ min)..."
	$(PYTHON) $(DATA_GEN)/generate_all.py

seed-fast: _check-pg
	@echo "[+] Generando datasets reducidos (modo --small, ~5 min)..."
	$(PYTHON) $(DATA_GEN)/generate_all.py --small

# Más específico primero: seed-ex-NN-full → dataset completo
seed-ex-%-full: _check-pg
	@echo "[+] Generando dataset completo para ejercicio $*..."
	$(PYTHON) $(DATA_GEN)/generate_all.py --exercise $*

# El ejercicio 04 necesita volumen full para que la latencia y p95/p99 sean visibles.
seed-ex-04: _check-pg
	@echo "[+] Generando dataset completo para ejercicio 04..."
	$(PYTHON) $(DATA_GEN)/generate_all.py --exercise 04

# seed-ex-NN usa --small por defecto para iterar rápido en clase
seed-ex-%: _check-pg
	@echo "[+] Generando dataset reducido para ejercicio $* (usa 'make seed-ex-$*-full' para el completo)..."
	$(PYTHON) $(DATA_GEN)/generate_all.py --exercise $* --small

# ── Acceso a Postgres ────────────────────────────────────────────────────────
psql:
	docker exec -it clase01-postgres psql -U $(PG_USER) -d $(PG_DB)

replica-psql:
	docker exec -it clase01-replica psql -U $(PG_USER) -d $(PG_DB)

# ── Ejercicios (abre JupyterLab apuntando al ejercicio) ─────────────────────
# Acepta make exercise-01, make exercise-1, make exercise-10, etc.
exercise-%:
	@PADDED=$$(printf '%02d' '$*') && \
	EXERCISE_DIR=$$(ls -d exercises/ex$$PADDED-* 2>/dev/null | head -1) && \
	if [ -z "$$EXERCISE_DIR" ]; then \
		echo "[!] No se encontró el ejercicio $$PADDED"; exit 1; \
	fi && \
	echo "[+] Abriendo JupyterLab para $$EXERCISE_DIR ..." && \
	$(JUPYTER) lab "$$EXERCISE_DIR/exercise.ipynb"

# ── Calidad de notebooks ─────────────────────────────────────────────────────
lint-notebooks:
	@echo "[+] Verificando notebooks con nbqa..."
	$(VENV)/bin/nbqa flake8 exercises/ --ignore=E501,W503 || true
	@echo "[+] Verificando que no haya salidas obsoletas..."
	$(JUPYTER) nbconvert --to notebook --execute --inplace exercises/**/exercise.ipynb 2>&1 | tail -5

# ── Ayuda ────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  clase01-intro — Comandos disponibles"
	@echo "  ─────────────────────────────────────"
	@echo "  make venv            Crea el venv e instala dependencias Python"
	@echo "  make venv-clean      Elimina el venv"
	@echo "  make up              Levanta postgres + réplica"
	@echo "  make up-admin        Levanta también pgAdmin en :8080"
	@echo "  make down            Para los contenedores"
	@echo "  make clean           Para y borra volúmenes (pide confirmación)"
	@echo "  make seed            Genera todos los datasets (full, lento)"
	@echo "  make seed-fast       Genera datasets reducidos (~5 min)"
	@echo "  make seed-ex-01      Genera dataset reducido del ejercicio 01 (--small)"
	@echo "  make seed-ex-01-full Genera dataset completo del ejercicio 01"
	@echo "  make seed-ex-02      Genera dataset reducido del ejercicio 02 (--small)"
	@echo "  make seed-ex-02-full Genera dataset completo del ejercicio 02"
	@echo "  make seed-ex-03      Genera dataset reducido del ejercicio 03 (--small)"
	@echo "  make seed-ex-03-full Genera dataset completo del ejercicio 03"
	@echo "  make seed-ex-04      Genera dataset completo del ejercicio 04"
	@echo "  make seed-ex-04-full Genera dataset completo del ejercicio 04"
	@echo "  make exercise-01     Abre el notebook del ejercicio 01"
	@echo "  make exercise-02     Abre el notebook del ejercicio 02"
	@echo "  make exercise-03     Abre el notebook del ejercicio 03"
	@echo "  make exercise-04     Abre el notebook del ejercicio 04"
	@echo "  make psql            Abre psql en la primaria"
	@echo "  make replica-psql    Abre psql en la réplica"
	@echo "  make lint-notebooks  Verifica los notebooks"
	@echo ""
