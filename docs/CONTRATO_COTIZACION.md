# Contrato de cálculo · Etapa 2

`POST /api/v1/cotizaciones/calcular` recibe un objeto JSON con los mismos campos que usa `GCIMT.quote` en el sistema JS y
devuelve el mismo resultado (claves camelCase). Así React reutiliza la lógica de presentación sin traducciones.

## Entrada (campos principales; todos los parámetros de la tabla de supuestos se aceptan igual que en JS)
| Campo | Significado |
|---|---|
| type | Camioneta, Rabón, Torton, Tráiler o Full (un nombre desconocido usa la base de Rabón, como en JS) |
| km | Kilómetros de ida (obligatorio, > 0) |
| loadTons | Carga en toneladas (no puede superar la capacidad de la unidad) |
| year | Año modelo, 2000–2026 |
| dieselPrice, dieselPriceIncludesIVA | Precio del diésel (10–60). Con `true` se divide entre 1.16 |
| tollsOneWay, tollsPriceIncludesIVA | Casetas de un sentido; el regreso se duplica |
| rows | `[{id, km}]` con las 7 clases viales; la suma no puede exceder `km` |
| elevationAvailable, ascent, descent | Altimetría de la ruta |
| travelHours | Horas de manejo de ida (si falta: km / 55) |
| operatorMode, operatorPerKm | `fijo` o `variable` |
| utility | Utilidad sobre costo, limitada a 0–0.50 (por defecto 0.08) |
| carrierAdminFactor, carrierPatioFactor, carrierUtilizationFactor | Perfil del transportista |
| tierPremiums | Porcentajes de CP, B, BP y SPOT |
| manualCosts | Importes manuales por rubro (`fixed`, `diesel`, `tolls`, …); vacío o nulo = automático |

## Salida (principales)
`tariff` (tarifa C), `cost`, `profit`, `fixedAllocation`, `variable` (9 rubros), `variableTotal`, `refTiers` (5 referencias),
`journeyHours`, `dieselLitres`, `monthly`, `warnings` y `audit` con todos los factores usados.

## Errores
HTTP 422 con `{"detail": "<mensaje>"}`; los mensajes son idénticos a los del JS (distancia inválida, carga fuera de
capacidad, año fuera de rango, clases que exceden la ruta, diésel inválido, costo manual inválido).

## Paridad con el JS
- `backend/tests/golden/quote_cases.json`: 271 casos (260 aleatorios con semilla fija y 11 explícitos; 19 esperan un error) generados con el motor JS.
- Si cambia `legacy/imt-cost-model.js`, regenerar: `node tools/generar_golden.js legacy/imt-cost-model.js backend/tests/golden/quote_cases.json`
  y volver a correr `pytest`. Una diferencia indica que el motor Python debe actualizarse (o que el cambio en JS fue intencional).
- Única diferencia deliberada: un porcentaje de referencia no numérico en `tierPremiums` se rechaza con error; el JS devolvería NaN.
