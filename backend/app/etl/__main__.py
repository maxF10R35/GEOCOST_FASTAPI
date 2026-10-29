"""Uso:
  python -m app.etl --legacy /data/legacy --ref /data/raw/ref_ruta_22oct2026.csv            (carga)
  python -m app.etl --legacy /data/legacy --ref /data/raw/ref_ruta_22oct2026.csv --dry-run  (solo valida, sin base)"""
import argparse
import sys

from .transform import construir


def imprimir(tablas):
    print(f"{'tabla':<24}{'origen':>9}{'cargadas':>10}{'dedup.':>8}{'rechaz.':>9}")
    for t in tablas:
        print(f"{t.nombre:<24}{t.filas_origen:>9}{len(t.rows):>10}{t.deduplicadas:>8}{len(t.rechazos):>9}")
    for t in tablas:
        for r in t.rechazos[:5]:
            print(f"  ! {t.nombre}: {r}")
        if len(t.rechazos) > 5:
            print(f"  ! {t.nombre}: ... y {len(t.rechazos) - 5} rechazos más")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default="/data/legacy")
    ap.add_argument("--ref", default="/data/raw/ref_ruta_22oct2026.csv")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    tablas = construir(a.legacy, a.ref)
    imprimir(tablas)
    if a.dry_run:
        print("\nDRY-RUN: no se tocó la base de datos.")
        return 0
    from .load import cargar
    resumen = cargar(tablas)
    print("\nCARGA OK y conteos reconciliados:", ", ".join(f"{n}={c}" for n, _, c, _, _ in resumen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
