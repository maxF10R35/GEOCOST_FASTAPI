# Paridad visual con GeoCost actual

Regla: React debe producir el mismo aspecto, botones y funciones que `legacy/`.

## Estrategia
1. Reutilizar `legacy/styles.css` completo (762 líneas) importado tal cual en React. No reescribir estilos.
2. Mantener los mismos `id` y `class` en el marcado de cada componente.
3. Reutilizar `legacy/assets/` (logo CEMEX y portada).
4. Migrar pantalla por pantalla y comparar contra capturas de referencia.

## Tokens (de :root en styles.css)
--blue #0000B3 · --red #F22331 · --navy #07395c · --ink #12324f · --line #dce6f0 · --bg #eef4f8 · --panel #ffffff · --good #def5e8 · --header-h clamp(59px,7.5vh,76px)

## Botones y acciones a conservar (de index.html)
Barra superior: Clientes, Bodegas, Servicios, Reportes, Salir, Iniciar, Pantalla completa.
Mapa: Mapa, Satélite, Relieve, IRA GeoRisk, Ver México, Buscar dirección en mapa, Confirmar punto, Ver en mapa.
Origen/destino: Buscar dirección de origen, Buscar dirección de destino, Consultar ZT, Detectar estados de ruta.
Unidad: Camioneta, Rabón, Torton, Tráiler, Full · Sacos, Granel.
Costos: Configurar costos, Aplicar y recalcular, Restaurar supuestos de este vehículo, Restaurar valores físicos automáticos, Añadir caseta, Quitar casetas agregadas, Limpiar ajustes y usar cálculos automáticos, Restablecer referencias.
Servicios/datos: Actualizar precios, Actualizar estaciones nacionales, Actualizar cotización.
Reportes: Generar memoria técnica, Imprimir / Guardar PDF, Cerrar.

## Capturas de referencia (hacer antes de migrar cada pantalla)
Ventana 1440x900, guardar en docs/paridad/: portada, mapa vacío, cotización con ruta, panel Configurar costos, comparativo de orígenes, reporte ejecutivo, Servicios, Clientes.
