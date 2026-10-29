"""Esquema inicial: catálogos, zonas territoriales, diésel, casetas y referencias de tarifa

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UP = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE estado (
  clave char(2) PRIMARY KEY,
  nombre text NOT NULL UNIQUE
);
CREATE TABLE estado_alias (
  alias_norm text PRIMARY KEY,
  clave char(2) NOT NULL REFERENCES estado(clave)
);

CREATE TABLE origen_tarifa (
  id_origen text PRIMARY KEY,
  nombre text NOT NULL
);

CREATE TABLE bodega (
  id serial PRIMARY KEY,
  nombre text NOT NULL UNIQUE,
  tipo text,
  prioridad text,
  lat double precision NOT NULL,
  lng double precision NOT NULL,
  geom geometry(Point,4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lng, lat), 4326)) STORED,
  id_origen_tarifa text REFERENCES origen_tarifa(id_origen)
);
CREATE INDEX bodega_geom_gix ON bodega USING gist (geom);

CREATE TABLE destino (
  id bigserial PRIMARY KEY,
  cemex_id text,
  nombre text NOT NULL,
  lat double precision NOT NULL,
  lng double precision NOT NULL,
  geom geometry(Point,4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lng, lat), 4326)) STORED,
  id_repetido boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX destino_uq ON destino (COALESCE(cemex_id, ''), nombre, lat, lng);
CREATE INDEX destino_cemex_idx ON destino (cemex_id);
CREATE INDEX destino_nombre_trgm ON destino USING gin (lower(nombre) gin_trgm_ops);
CREATE INDEX destino_geom_gix ON destino USING gist (geom);

CREATE TABLE ubicacion_oficial (
  id text PRIMARY KEY,
  nombre text NOT NULL,
  tipo text,
  estado_clave char(2) REFERENCES estado(clave),
  estado_texto text,
  ciudad text,
  direccion text,
  url text,
  alias_existente text,
  coordenadas_verificadas boolean NOT NULL DEFAULT false,
  lat double precision,
  lng double precision,
  geom geometry(Point,4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lng, lat), 4326)) STORED
);

CREATE TABLE zona_territorial (
  zt_id text PRIMARY KEY,
  nombre text,
  municipio text,
  estado_clave char(2) NOT NULL REFERENCES estado(clave),
  geom geometry(MultiPolygon,4326) NOT NULL,
  centroide geometry(Point,4326) NOT NULL,
  ancho_km real
);
CREATE INDEX zt_geom_gix ON zona_territorial USING gist (geom);
CREATE INDEX zt_centroide_gix ON zona_territorial USING gist (centroide);
CREATE INDEX zt_estado_idx ON zona_territorial (estado_clave);

CREATE TABLE diesel_corte (
  fecha_corte date PRIMARY KEY,
  fuente text,
  fuente_url text,
  precio_nacional numeric(6,2),
  recuperado date,
  nota text
);
CREATE TABLE diesel_estado_precio (
  fecha_corte date NOT NULL REFERENCES diesel_corte(fecha_corte),
  estado_clave char(2) NOT NULL REFERENCES estado(clave),
  precio numeric(6,2) NOT NULL,
  estaciones integer,
  PRIMARY KEY (fecha_corte, estado_clave)
);

CREATE TABLE caseta_tarifa (
  id text PRIMARY KEY,
  nombre text NOT NULL,
  tramo text,
  modo text,
  red text,
  vigencia date,
  pagina integer,
  fuente_url text,
  fuente_sha256 text
);
CREATE TABLE caseta_tarifa_clase (
  caseta_id text NOT NULL REFERENCES caseta_tarifa(id) ON DELETE CASCADE,
  clase text NOT NULL,
  importe_con_iva numeric(8,2) NOT NULL,
  PRIMARY KEY (caseta_id, clase)
);

CREATE TABLE ref_ruta (
  id_ruta text PRIMARY KEY,
  id_origen text NOT NULL REFERENCES origen_tarifa(id_origen),
  zt_id text NOT NULL,
  zt_conocida boolean NOT NULL,
  estado_clave char(2) REFERENCES estado(clave),
  municipio text,
  tipo_conexion text NOT NULL,
  kms numeric(8,1),
  n_llaves integer,
  n_fleteros integer,
  tarifa_min numeric(12,2),
  tarifa_mediana numeric(12,2),
  tarifa_max numeric(12,2),
  base_mediana numeric(12,2),
  ajustes_mediana numeric(12,2),
  casetas_mediana numeric(12,2),
  n_con_casetas integer,
  tiene_casetas boolean NOT NULL,
  fecha_mas_reciente date,
  mxn_por_km_mediana numeric(10,2)
);
CREATE INDEX ref_ruta_origen_tipo_idx ON ref_ruta (id_origen, tipo_conexion);
CREATE INDEX ref_ruta_zt_idx ON ref_ruta (zt_id);

CREATE VIEW v_ref_ruta_geo AS
SELECT r.*, z.centroide, z.ancho_km, ST_Y(z.centroide) AS lat_zt, ST_X(z.centroide) AS lng_zt
FROM ref_ruta r JOIN zona_territorial z ON z.zt_id = r.zt_id;

CREATE TABLE tarifa_historica (
  id bigserial PRIMARY KEY,
  id_tarifa text NOT NULL,
  clase text NOT NULL,
  fecha_inicio date NOT NULL,
  importe_viaje numeric(14,4),
  id_ruta text,
  id_tabla text,
  id_origen text,
  zt_id text,
  tipo_conexion text,
  id_destinatario text,
  id_transportista text,
  id_ruta_tarifa text,
  importe numeric(14,4),
  moneda text,
  um text,
  fecha_fin date,
  fecha_modificacion date,
  primera_foto date,
  ultima_foto date
);
CREATE UNIQUE INDEX tarifa_historica_version_uq ON tarifa_historica (id_tarifa, clase, fecha_inicio, COALESCE(importe_viaje, -1));
CREATE INDEX tarifa_historica_ruta_idx ON tarifa_historica (id_ruta);

CREATE TABLE etl_carga (
  id serial PRIMARY KEY,
  tabla text NOT NULL,
  archivo text,
  sha256 text,
  filas_origen integer,
  filas_cargadas integer,
  deduplicadas integer,
  rechazadas integer,
  cargado_en timestamptz NOT NULL DEFAULT now(),
  notas text
)
"""

DOWN = """
DROP TABLE IF EXISTS etl_carga;
DROP TABLE IF EXISTS tarifa_historica;
DROP VIEW IF EXISTS v_ref_ruta_geo;
DROP TABLE IF EXISTS ref_ruta;
DROP TABLE IF EXISTS caseta_tarifa_clase;
DROP TABLE IF EXISTS caseta_tarifa;
DROP TABLE IF EXISTS diesel_estado_precio;
DROP TABLE IF EXISTS diesel_corte;
DROP TABLE IF EXISTS zona_territorial;
DROP TABLE IF EXISTS ubicacion_oficial;
DROP TABLE IF EXISTS destino;
DROP TABLE IF EXISTS bodega;
DROP TABLE IF EXISTS origen_tarifa;
DROP TABLE IF EXISTS estado_alias;
DROP TABLE IF EXISTS estado
"""


def _run(sql: str) -> None:
    for stmt in (s.strip() for s in sql.split(";\n")):
        if stmt:
            op.execute(stmt)


def upgrade() -> None:
    _run(UP)


def downgrade() -> None:
    _run(DOWN)
