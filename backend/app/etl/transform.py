"""Extracción y transformación (sin base de datos): lee los archivos fuente, valida, limpia y devuelve filas listas
para cargar. Todo lo descartado queda en `rechazos` y todo lo deduplicado en `deduplicadas`; nada se pierde en silencio."""
import csv
import glob
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field

from .estados import ESTADOS, ALIAS, clave_estado

LAT = (14.0, 33.5)
LNG = (-119.0, -86.0)
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Tabla:
    nombre: str
    cols: list
    rows: list = field(default_factory=list)
    archivo: str = ""
    sha256: str = ""
    filas_origen: int = 0
    deduplicadas: int = 0
    rechazos: list = field(default_factory=list)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _f(x):
    s = "" if x is None else str(x).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return None if math.isnan(v) else v


def _i(x):
    v = _f(x)
    return None if v is None else int(round(v))


def _fecha(x):
    s = str(x or "").strip()[:10]
    return s if FECHA.match(s) else None


def _txt(x):
    s = "" if x is None else str(x).strip()
    return s or None


def _en_mexico(lat, lng):
    return lat is not None and lng is not None and LAT[0] <= lat <= LAT[1] and LNG[0] <= lng <= LNG[1]


def _nuevo(nombre, cols, path):
    return Tabla(nombre, cols, archivo=os.path.basename(path), sha256=_sha(path))


def estados():
    t = Tabla("estado", ["clave", "nombre"], rows=[(c, n) for c, n, _ in ESTADOS], filas_origen=len(ESTADOS))
    a = Tabla("estado_alias", ["alias_norm", "clave"], rows=sorted(ALIAS.items()), filas_origen=len(ALIAS))
    return t, a


def ref_ruta(csv_path, zt_conocidas):
    t = Tabla("ref_ruta", ["id_ruta", "id_origen", "zt_id", "zt_conocida", "estado_clave", "municipio",
                           "tipo_conexion", "kms", "n_llaves", "n_fleteros", "tarifa_min", "tarifa_mediana",
                           "tarifa_max", "base_mediana", "ajustes_mediana", "casetas_mediana", "n_con_casetas",
                           "tiene_casetas", "fecha_mas_reciente", "mxn_por_km_mediana"],
              archivo=os.path.basename(csv_path), sha256=_sha(csv_path))
    origenes = {}
    vistos = set()
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for n, r in enumerate(csv.DictReader(fh), start=2):
            t.filas_origen += 1
            idr = _txt(r.get("ID_RUTA"))
            ido, zt, tipo = _txt(r.get("IdOrigen")), _txt(r.get("ZonaDestino")), _txt(r.get("TipoConexion"))
            if not (idr and ido and zt and tipo):
                t.rechazos.append(f"línea {n}: falta ID_RUTA, origen, zona o tipo de conexión")
                continue
            if idr in vistos:
                t.deduplicadas += 1
                continue
            vistos.add(idr)
            origenes[ido] = _txt(r.get("Origen")) or ido
            est = _txt(r.get("Estado"))
            t.rows.append((idr, ido, zt, zt in zt_conocidas, clave_estado(est) if est else None, _txt(r.get("Municipio")),
                           tipo, _f(r.get("Kms")), _i(r.get("n_llaves")), _i(r.get("n_fleteros")),
                           _f(r.get("Tarifa_Min")), _f(r.get("Tarifa_Mediana")), _f(r.get("Tarifa_Max")),
                           _f(r.get("Base_Mediana")), _f(r.get("Ajustes_Mediana")), _f(r.get("Casetas_Mediana")),
                           _i(r.get("n_con_casetas")), str(r.get("Tiene_Casetas")).strip().lower() in ("true", "1", "si", "sí"),
                           _fecha(r.get("Fecha_Mas_Reciente")), _f(r.get("MXN_por_km_mediana"))))
    o = Tabla("origen_tarifa", ["id_origen", "nombre"], rows=sorted(origenes.items()), filas_origen=len(origenes))
    return o, t


def bodegas(legacy, ids_origen):
    p = os.path.join(legacy, "bodegas.json")
    t = Tabla("bodega", ["nombre", "tipo", "prioridad", "lat", "lng", "id_origen_tarifa"],
              archivo="bodegas.json", sha256=_sha(p))
    mapa = _json(os.path.join(legacy, "origen_map.json"))
    nombres = set()
    for item in _json(p):
        t.filas_origen += 1
        nombre, ll, tipo, prio = item[0], item[1], item[2], item[3]
        lat, lng = _f(ll[0]), _f(ll[1])
        if nombre in nombres or not _en_mexico(lat, lng):
            t.rechazos.append(f"{nombre}: nombre repetido o coordenadas fuera de México")
            continue
        nombres.add(nombre)
        ido = mapa.get(nombre)
        if ido and ido not in ids_origen:
            t.rechazos.append(f"{nombre}: IdOrigen {ido} no existe en la base de tarifas (se carga sin equivalente)")
            ido = None
        t.rows.append((nombre, tipo, prio, lat, lng, ido))
    return t


def destinos(legacy):
    p = os.path.join(legacy, "frentes.json")
    t = Tabla("destino", ["cemex_id", "nombre", "lat", "lng", "id_repetido"], archivo="frentes.json", sha256=_sha(p))
    vistos, filas = set(), []
    for x in _json(p):
        t.filas_origen += 1
        cid, nombre = _txt(x.get("cemex_id")), _txt(x.get("nombre"))
        lat, lng = _f(x.get("lat")), _f(x.get("lng"))
        if not nombre or not _en_mexico(lat, lng):
            t.rechazos.append(f"{cid}/{nombre}: sin nombre o coordenadas fuera de México")
            continue
        k = (cid or "", nombre, lat, lng)
        if k in vistos:
            t.deduplicadas += 1
            continue
        vistos.add(k)
        filas.append((cid, nombre, lat, lng))
    cuenta = {}
    for cid, *_ in filas:
        if cid:
            cuenta[cid] = cuenta.get(cid, 0) + 1
    t.rows = [(cid, n, la, ln, bool(cid) and cuenta[cid] > 1) for cid, n, la, ln in filas]
    return t


def oficiales(legacy):
    p = os.path.join(legacy, "cemex-ubicaciones-oficiales.json")
    t = Tabla("ubicacion_oficial", ["id", "nombre", "tipo", "estado_clave", "estado_texto", "ciudad", "direccion", "url",
                                    "alias_existente", "coordenadas_verificadas", "lat", "lng"],
              archivo="cemex-ubicaciones-oficiales.json", sha256=_sha(p))
    for x in _json(p)["locations"]:
        t.filas_origen += 1
        lat, lng = _f(x.get("lat")), _f(x.get("lng"))
        if not _en_mexico(lat, lng):
            lat = lng = None
        t.rows.append((x["id"], x["name"], _txt(x.get("kind")), clave_estado(x.get("state")), _txt(x.get("state")),
                       _txt(x.get("city")), _txt(x.get("address")), _txt(x.get("url")), _txt(x.get("existingAlias")),
                       bool(x.get("coordinatesVerified")) and lat is not None, lat, lng))
    return t


def _anillo(r):
    pts = [(float(a), float(b)) for a, b in r]
    if len(pts) and pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 4 or not all(_en_mexico(b, a) for a, b in pts):
        return None
    return pts


def zonas(legacy):
    t = Tabla("zona_territorial", ["zt_id", "nombre", "municipio", "estado_clave", "wkt", "ancho_km"],
              archivo="zt/*.json", sha256="")
    h = hashlib.sha256()
    ids = set()
    for p in sorted(glob.glob(os.path.join(legacy, "zt", "*.json"))):
        if p.endswith("index.json"):
            continue
        h.update(_sha(p).encode())
        for z in _json(p):
            t.filas_origen += 1
            zid = _txt(z.get("id"))
            clave = clave_estado(z.get("estado"))
            anillos = [a for a in (_anillo(r) for r in z.get("rings", [])) if a]
            if not zid or zid in ids or not clave or not anillos:
                t.rechazos.append(f"{zid}: id repetido o vacío, estado «{z.get('estado')}» sin clave, o geometría inválida")
                continue
            ids.add(zid)
            wkt = "MULTIPOLYGON(" + ",".join("((" + ",".join(f"{a:.6f} {b:.6f}" for a, b in an) + "))" for an in anillos) + ")"
            bb = z["bbox"]
            ancho = round((bb[2] - bb[0]) * 111.32 * math.cos(math.radians((bb[1] + bb[3]) / 2)), 1)
            t.rows.append((zid, _txt(z.get("nombre")), _txt(z.get("municipio")), clave, wkt, ancho))
    t.sha256 = h.hexdigest()
    return t


def diesel(legacy):
    p = os.path.join(legacy, "diesel-estados.json")
    d = _json(p)
    fecha = _fecha(d.get("observationDate"))
    c = Tabla("diesel_corte", ["fecha_corte", "fuente", "fuente_url", "precio_nacional", "recuperado", "nota"],
              archivo="diesel-estados.json", sha256=_sha(p), filas_origen=1)
    if not fecha:
        c.rechazos.append("observationDate inválida")
    else:
        c.rows.append((fecha, _txt(d.get("source")), _txt(d.get("sourceUrl")), _f(d.get("nationalPrice")),
                       _fecha(d.get("retrievedDate")), _txt(d.get("note"))))
    e = Tabla("diesel_estado_precio", ["fecha_corte", "estado_clave", "precio", "estaciones"],
              archivo="diesel-estados.json", sha256=c.sha256)
    vistos = set()
    for s in d["states"]:
        e.filas_origen += 1
        clave, precio = clave_estado(s.get("state")), _f(s.get("diesel"))
        if not fecha or not clave or precio is None or not (5 <= precio <= 70) or clave in vistos:
            e.rechazos.append(f"{s.get('state')}: estado sin clave, precio inválido o repetido")
            continue
        vistos.add(clave)
        e.rows.append((fecha, clave, precio, _i(s.get("stations"))))
    return c, e


def casetas(legacy):
    p = os.path.join(legacy, "capufe-tarifas.json")
    d = _json(p)
    sha = _sha(p)
    c = Tabla("caseta_tarifa", ["id", "nombre", "tramo", "modo", "red", "vigencia", "pagina", "fuente_url", "fuente_sha256"],
              archivo="capufe-tarifas.json", sha256=sha)
    k = Tabla("caseta_tarifa_clase", ["caseta_id", "clase", "importe_con_iva"], archivo="capufe-tarifas.json", sha256=sha)
    ids = set()
    for x in d["records"]:
        c.filas_origen += 1
        if not x.get("id") or x["id"] in ids or not x.get("name"):
            c.rechazos.append(f"{x.get('id')}: id vacío o repetido")
            continue
        ids.add(x["id"])
        c.rows.append((x["id"], x["name"], _txt(x.get("section")), _txt(x.get("mode")), _txt(x.get("network")),
                       _fecha(x.get("effective")), _i(x.get("page")), _txt(d.get("sourceUrl")), d.get("sha256") or sha))
        for clase, imp in (x.get("rates") or {}).items():
            k.filas_origen += 1
            v = _f(imp)
            if v is None or v < 0:
                k.rechazos.append(f"{x['id']}/{clase}: importe inválido")
                continue
            k.rows.append((x["id"], clase, v))
    return c, k


def construir(legacy, ref_csv):
    """Devuelve las tablas en orden de carga (respeta las llaves foráneas)."""
    est, ali = estados()
    zt = zonas(legacy)
    org, ref = ref_ruta(ref_csv, {r[0] for r in zt.rows})
    bod = bodegas(legacy, {r[0] for r in org.rows})
    des, ofi = destinos(legacy), oficiales(legacy)
    dc, de = diesel(legacy)
    ca, cc = casetas(legacy)
    return [est, ali, org, bod, des, ofi, zt, dc, de, ca, cc, ref]
