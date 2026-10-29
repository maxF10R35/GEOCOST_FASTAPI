"""Pruebas de la capa de transformación (no necesitan base de datos). Usan los datos reales si están montados."""
import os
from pathlib import Path

from app.etl import transform
from app.etl.estados import ESTADOS, clave_estado, norm

LEGACY = Path(os.environ.get("GEOCOST_LEGACY", "/data/legacy"))
REF = Path(os.environ.get("GEOCOST_REF", "/data/raw/ref_ruta_22oct2026.csv"))


def _necesita_datos():
    if not LEGACY.exists() or not REF.exists():
        import pytest
        pytest.skip("datos no montados (LEGACY/REF)")


def test_estados_reconcilian_variantes():
    assert len(ESTADOS) == 32
    casos = {"Edo de Mexico": "15", "Estado de México": "15", "Distrito Federal": "09", "Ciudad de Mexico": "09",
             "Baja California S": "03", "Veracruz de Ignacio": "30", "Guanajuato-ZT.KML": "11", "Michoacan": "16"}
    for nombre, clave in casos.items():
        assert clave_estado(nombre) == clave, nombre
    assert clave_estado("Narnia") is None
    assert norm("Edo. de México") == "edodemexico"


def test_conteos_y_reconciliacion():
    _necesita_datos()
    tablas = {t.nombre: t for t in transform.construir(str(LEGACY), str(REF))}
    for t in tablas.values():
        assert t.filas_origen == len(t.rows) + t.deduplicadas + len(t.rechazos), t.nombre
    assert len(tablas["estado"].rows) == 32
    assert len(tablas["bodega"].rows) == 58
    assert len(tablas["zona_territorial"].rows) == 23666 and not tablas["zona_territorial"].rechazos
    assert len(tablas["diesel_estado_precio"].rows) == 32 and not tablas["diesel_estado_precio"].rechazos
    assert len(tablas["caseta_tarifa"].rows) == 233
    assert len(tablas["ref_ruta"].rows) == 29335


def test_destinos_dedupe_y_marca_de_id_repetido():
    _necesita_datos()
    t = transform.destinos(str(LEGACY))
    assert t.deduplicadas > 0 and len(t.rows) == t.filas_origen - t.deduplicadas - len(t.rechazos)
    llaves = {(r[0] or "", r[1], r[2], r[3]) for r in t.rows}
    assert len(llaves) == len(t.rows)  # sin duplicados exactos
    assert any(r[4] for r in t.rows)  # hay ids repetidos con ubicaciones distintas, marcados


def test_zonas_wkt_y_llaves_foraneas():
    _necesita_datos()
    tablas = {t.nombre: t for t in transform.construir(str(LEGACY), str(REF))}
    zt = tablas["zona_territorial"]
    assert all(r[4].startswith("MULTIPOLYGON(((") for r in zt.rows)
    claves = {r[0] for r in tablas["estado"].rows}
    assert all(r[3] in claves for r in zt.rows)
    ids_origen = {r[0] for r in tablas["origen_tarifa"].rows}
    assert all(r[5] is None or r[5] in ids_origen for r in tablas["bodega"].rows)
    assert all(r[1] in ids_origen for r in tablas["ref_ruta"].rows)
    desconocidas = [r for r in tablas["ref_ruta"].rows if not r[3]]
    assert 0 < len(desconocidas) < 50  # ZT de tarifas que no existen en los polígonos: se conservan, marcadas
