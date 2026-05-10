#!/usr/bin/env python3
"""
Orquestador de generación de datos para clase01-intro.
Uso:
  python generate_all.py                  # genera todos los ejercicios disponibles (full)
  python generate_all.py --small          # datasets reducidos de ejercicios disponibles
  python generate_all.py --exercise 1     # solo el ejercicio 1
  python generate_all.py --exercise 1 --small
"""

import argparse
import importlib
import sys
import time

EXERCISES = {
    1: ("ex01_schema_rigidity", "Ejercicio 01 — Evolución de Esquema y EAV"),
    2: ("ex02_impedance_mismatch", "Ejercicio 02 — Impedance Mismatch"),
    3: ("ex03_reporting_preaggregation", "Ejercicio 03 — Reporting y Preagregación"),
    4: ("ex04_hot_reads_latency", "Ejercicio 04 — Hot Reads y Latencia"),
}


def main():
    parser = argparse.ArgumentParser(description="Genera datasets para clase01-intro")
    parser.add_argument("--small", action="store_true", help="Genera datasets reducidos (~10%)")
    parser.add_argument("--exercise", type=int, help="Genera solo el ejercicio N")
    args = parser.parse_args()

    if args.exercise and args.exercise not in EXERCISES:
        print(f"[ERROR] Ejercicio {args.exercise} no existe. Válidos: {list(EXERCISES.keys())}")
        sys.exit(1)

    targets = {args.exercise: EXERCISES[args.exercise]} if args.exercise else EXERCISES

    total_start = time.time()
    errors = []

    for num, (module_name, label) in targets.items():
        print(f"\n{'='*60}")
        print(f"  {label}")
        if args.small:
            print("  [modo --small: dataset reducido]")
        print(f"{'='*60}")
        try:
            mod = importlib.import_module(module_name)
            mod.run(small=args.small)
        except Exception as e:
            print(f"\n[ERROR] Ejercicio {num} falló: {e}")
            errors.append((num, str(e)))

    elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  Generación completada en {elapsed:.1f}s")
    if errors:
        print(f"  ERRORES en ejercicios: {[n for n, _ in errors]}")
        for num, err in errors:
            print(f"    Ex{num:02d}: {err}")
        sys.exit(1)
    else:
        print("  Todos los datasets generados correctamente.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
