"""Carga a PostgreSQL/PostGIS. Recarga completa de catálogos en UNA transacción: o queda todo o no cambia nada.
Después reconcilia conteos (origen = cargadas + deduplicadas + rechazadas) y registra la corrida en etl_carga."""
import psycopg

from app.core.config import settings

from .transform import Tabla

ORDEN_TRUNCATE = ("ref_ruta, caseta_tarifa_clase, caseta_tarifa, diesel_estado_precio, diesel_corte, zona_territorial, "
                  "ubicacion_oficial, destino, bodega, origen_tarifa, estado_alias, estado")


def dsn() -> str:
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://")


def _copy(cur, tabla: str, cols, rows):
    with cur.copy(f"COPY {tabla} ({', '.join(cols)}) FROM STDIN") as cp:
        for r in rows:
            cp.write_row(r)


def _cargar_zonas(cur, t: Tabla):
    cur.execute("CREATE TEMP TABLE stg_zt (zt_id text, nombre text, municipio text, estado_clave char(2), wkt text, "
                "ancho_km real) ON COMMIT DROP")
    _copy(cur, "stg_zt", t.cols, t.rows)
    cur.execute("""
        INSERT INTO zona_territorial (zt_id, nombre, municipio, estado_clave, geom, centroide, ancho_km)
        SELECT zt_id, nombre, municipio, estado_clave, g, ST_Centroid(g), ancho_km
        FROM (SELECT *, ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromText(wkt, 4326)), 3)) AS g FROM stg_zt) s
        WHERE g IS NOT NULL AND NOT ST_IsEmpty(g)
    """)


def cargar(tablas: list[Tabla]) -> list[tuple]:
    resumen = []
    with psycopg.connect(dsn()) as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(f"TRUNCATE {ORDEN_TRUNCATE} RESTART IDENTITY CASCADE")
            for t in tablas:
                if t.nombre == "zona_territorial":
                    _cargar_zonas(cur, t)
                else:
                    _copy(cur, t.nombre, t.cols, t.rows)
                cur.execute(f"SELECT count(*) FROM {t.nombre}")
                en_bd = cur.fetchone()[0]
                perdidas = len(t.rows) - en_bd
                if perdidas:
                    raise RuntimeError(f"{t.nombre}: se esperaban {len(t.rows)} filas y la base tiene {en_bd}")
                if t.filas_origen != len(t.rows) + t.deduplicadas + len(t.rechazos):
                    raise RuntimeError(f"{t.nombre}: no cuadra origen={t.filas_origen} cargadas={len(t.rows)} "
                                       f"dedup={t.deduplicadas} rechazadas={len(t.rechazos)}")
                cur.execute("INSERT INTO etl_carga (tabla, archivo, sha256, filas_origen, filas_cargadas, deduplicadas, "
                            "rechazadas, notas) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (t.nombre, t.archivo, t.sha256, t.filas_origen, en_bd, t.deduplicadas, len(t.rechazos),
                             "; ".join(t.rechazos[:10]) or None))
                resumen.append((t.nombre, t.filas_origen, en_bd, t.deduplicadas, len(t.rechazos)))
            cur.execute("SELECT count(*) FROM zona_territorial WHERE NOT ST_IsValid(geom)")
            invalidas = cur.fetchone()[0]
            if invalidas:
                raise RuntimeError(f"zona_territorial: {invalidas} geometrías inválidas tras ST_MakeValid")
    return resumen
