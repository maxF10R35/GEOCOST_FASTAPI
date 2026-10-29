# Modelo de datos · Etapa 1

PostgreSQL 16 + PostGIS 3.4. Migraciones con Alembic (`0001_esquema_inicial`). Carga con `python -m app.etl`.

## Tablas
| Tabla | Contenido | Filas esperadas |
|---|---|---|
| estado / estado_alias | 32 estados (clave INEGI) y variantes de escritura | 32 / 42 |
| origen_tarifa | Orígenes de la base de tarifas (IdOrigen) | 278 |
| bodega | Bodegas del cotizador, ligadas a origen_tarifa (51 de 58) | 58 |
| destino | Clientes y frentes, con índice de búsqueda por nombre (trigramas) y espacial | 22,350 |
| ubicacion_oficial | Fichas públicas de CEMEX (coordenadas sin verificar) | 33 |
| zona_territorial | Polígonos ZT (MultiPolygon) y centroide | 23,666 |
| diesel_corte / diesel_estado_precio | Precio de diésel por estado y fecha de corte | 1 / 32 |
| caseta_tarifa / caseta_tarifa_clase | Tarifas CAPUFE/FONADIN por clase (con IVA) | 233 / 3,495 |
| ref_ruta | Referencias de tarifa por origen, zona y tipo de conexión | 29,335 |
| tarifa_historica | Histórico de tarifas (solo agregar). Se crea vacía; se carga en la Etapa 1b | 0 |
| etl_carga | Bitácora: archivo, huella SHA-256 y conteos de cada carga | 12 por corrida |

Vista `v_ref_ruta_geo`: ref_ruta unida con el centroide de su ZT (base de la búsqueda de referencias de la Etapa 3).

## Hallazgos de calidad de datos (detectados al construir el ETL)
1. **Clientes con ID repetido:** frentes.json trae 22,869 filas, pero 519 son duplicados exactos (se descartan y se cuentan). Quedan 22,350; los CEMEX ID que aún se repiten con ubicaciones distintas se conservan y se marcan con `id_repetido`. 26 filas del origen no tienen CEMEX ID (se guardan con ID nulo). Tras la limpieza, 1,064 filas quedan marcadas con `id_repetido`.
2. **Estados con nombres distintos** en cada fuente (ZT, diésel, tarifas). Se reconcilian a la clave INEGI con una tabla de alias. El ETL falla si aparece un estado sin clave: así se detectó «Veracruz de Ignacio» (2,134 zonas).
3. **ZT en tarifas sin polígono:** 20 filas de ref_ruta apuntan a 6 códigos que no existen en los polígonos (`0000000000`, `EE00`, `BZLDV001`, `GEIGPA0001`, `MXALCO0024`, `OXSJPT0002`). Se conservan con `zt_conocida = false` y no entran en la vista geográfica.
4. **Casetas con vigencia vieja:** 31 de 233 tienen vigencia 2023-07-01; el resto 2026-04-13. La columna `vigencia` permite avisarlo en el cotizador.
5. **9 ZT con más de un anillo.** Cada anillo se carga como una parte del MultiPolygon (supuesto: son partes, no huecos). Revisar en el mapa.
6. **7 bodegas sin equivalente** en la base de tarifas (Huatulco, Progreso, Huejutla, Trinitaria, Huautla y los dos Medias Aguas): `id_origen_tarifa` queda nulo.

## Reglas del ETL
- Recarga completa de catálogos en una sola transacción: o queda todo o no cambia nada.
- Reconciliación obligatoria: filas de origen = cargadas + deduplicadas + rechazadas, y conteo en base = filas cargadas.
- Nada se descarta en silencio: los rechazos se reportan y se guardan en `etl_carga.notas`.
- Los precios de diésel y las casetas se guardan **con IVA**, como en la fuente. El modelo de costos divide entre 1.16 (Etapa 2).
