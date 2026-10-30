"""Motor de costos GeoCost SC (modelo IMT 630, variante operativa de calibración V1).

Port 1:1 de `imt-cost-model.js` (función `quote`). Mantiene el MISMO contrato (claves camelCase de entrada y salida) para
que el frontend React reutilice la lógica de presentación actual. Las pruebas de paridad (tests/test_paridad_motor.py)
comparan este módulo contra resultados generados por el motor JavaScript.

Los coeficientes por vehículo, año y pendiente son HIPÓTESIS EDITABLES, no cifras oficiales IMT ni tarifas de mercado.
"""
from __future__ import annotations

import math
import re
from typing import Any

_UNDEF = object()  # equivale a `undefined` de JavaScript (clave ausente)
_NUM = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")

DEFS: dict[str, dict[str, Any]] = {
    "Camioneta": {"cap": 5, "kml": 7.5, "empty": 9.0, "kmMonth": 6000, "fixed": {"asset": 13000, "operator": 9500, "insurance": 1800, "admin": 2300, "permit": 300, "gps": 400, "patio": 700}, "tires": {"count": 6, "price": 3800, "life": 45000}, "maintenance": 1.0, "lubes": 0.20, "def": 0, "idle": 1.2},
    "Rabón": {"cap": 9, "kml": 3.6, "empty": 4.8, "kmMonth": 7000, "fixed": {"asset": 26000, "operator": 16500, "insurance": 3500, "admin": 3800, "permit": 600, "gps": 700, "patio": 1800}, "tires": {"count": 6, "price": 9000, "life": 65000}, "maintenance": 1.9, "lubes": 0.35, "def": 0.025, "idle": 1.7},
    "Torton": {"cap": 18, "kml": 3.0, "empty": 4.1, "kmMonth": 7500, "fixed": {"asset": 36000, "operator": 19500, "insurance": 5700, "admin": 5100, "permit": 900, "gps": 900, "patio": 2400}, "tires": {"count": 10, "price": 9500, "life": 70000}, "maintenance": 2.6, "lubes": 0.46, "def": 0.03, "idle": 1.9},
    "Tráiler": {"cap": 28, "kml": 2.5, "empty": 3.4, "kmMonth": 9000, "fixed": {"asset": 50000, "operator": 22500, "insurance": 11000, "admin": 6000, "permit": 1250, "gps": 1000, "patio": 3800}, "tires": {"count": 18, "price": 11000, "life": 80000}, "maintenance": 3.15, "lubes": 0.55, "def": 0.035, "idle": 2.3},
    "Full": {"cap": 50, "kml": 1.65, "empty": 2.2, "kmMonth": 10000, "fixed": {"asset": 71000, "operator": 26000, "insurance": 14000, "admin": 7500, "permit": 1800, "gps": 1200, "patio": 5500}, "tires": {"count": 26, "price": 11500, "life": 80000}, "maintenance": 4.2, "lubes": 0.7, "def": 0.04, "idle": 2.8},
}
CARRIER_PROFILES = {
    "chico": {"fleet": "1–5", "exampleUnits": 3, "admin": 0.70, "patio": 0.65, "utilization": 1},
    "mediano": {"fleet": "6–15", "exampleUnits": 10, "admin": 1, "patio": 1, "utilization": 1},
    "grande": {"fleet": "16+", "exampleUnits": 25, "admin": 1.28, "patio": 1.35, "utilization": 1},
}
TIER_DEFAULTS = [
    {"id": "C", "name": "C", "pct": 0}, {"id": "CP", "name": "C´", "pct": 4}, {"id": "B", "name": "B", "pct": 9},
    {"id": "BP", "name": "B+", "pct": 14}, {"id": "SPOT", "name": "B SPOT", "pct": 20},
]
CLASSES = ["urbano", "autopista_sin", "autopista_con", "pavimento_sin", "pavimento_con", "terraceria_sin", "terraceria_con"]


# ---- utilidades que replican la semántica numérica de JavaScript ----------------------------------------------
def _num(x: Any) -> float:
    """Number(x) de JavaScript."""
    if x is _UNDEF:
        return math.nan
    if x is None:
        return 0.0
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return 0.0
        return float(s) if _NUM.match(s) else math.nan
    return math.nan


def _val(obj: Any, key: str, default: float = 0.0) -> float:
    """val(obj,k,def): número finito presente (no vacío ni nulo) o el valor por defecto."""
    raw = obj.get(key, _UNDEF) if isinstance(obj, dict) else _UNDEF
    n = _num(raw)
    if math.isfinite(n) and raw is not _UNDEF and raw is not None and raw != "":
        return n
    return default


def _clamp(v: Any, a: float, b: float) -> float:
    n = _num(v)
    if math.isnan(n) or n == 0:
        n = 0.0
    return min(b, max(a, n))


def _jsround(x: float) -> float:
    return math.floor(x + 0.5)  # Math.round: mitades hacia arriba (Python redondea a par)


def _fmt(x: float) -> str:
    """Número como lo imprime JavaScript en una plantilla de texto."""
    return str(int(x)) if x == int(x) else repr(x)


def _preset(kind: Any) -> dict[str, Any]:
    import copy
    return copy.deepcopy(DEFS.get(kind) or DEFS["Rabón"])


def _ages(year: float) -> dict[str, Any]:
    y = _clamp(year, 2000, 2026)
    oldness = 2026 - y
    return {"period": f"{_fmt(y)} (edad {_fmt(oldness)} años)", "consumption": max(0.76, 1 - 0.009 * oldness),
            "maintenance": 1 + 0.019 * oldness, "tires": 1 + 0.0045 * oldness}


def _classification(km: float, items: Any) -> dict[str, Any]:
    ledger = {k: 0.0 for k in CLASSES}
    for item in items or []:
        if isinstance(item, dict) and item.get("id") in CLASSES:
            n = _num(item.get("km", _UNDEF))
            ledger[item["id"]] += max(0.0, 0.0 if math.isnan(n) or n == 0 else n)
    known = sum(ledger.values())
    return {"ledger": ledger, "known": known, "unknownKm": max(0.0, km - known), "valid": known <= km + 0.1}


def references(tariff: float, premiums: Any) -> list[dict[str, Any]]:
    out = []
    for t in TIER_DEFAULTS:
        raw = premiums.get(t["id"]) if isinstance(premiums, dict) else None
        pct = t["pct"] if raw is None else _num(raw)
        if math.isnan(pct):
            raise ValueError("Porcentaje de referencia inválido: " + t["id"])  # JS devolvería NaN; aquí se rechaza
        pct = max(0, min(100, pct))
        out.append({"id": t["id"], "name": t["name"], "pct": pct, "amount": tariff * (1 + pct / 100)})
    return out


def quote(inp: dict[str, Any] | None = None) -> dict[str, Any]:
    inp = inp or {}
    type_ = inp.get("type") or "Rabón"
    basis = _preset(type_)
    one = _val(inp, "km", 0)
    ton = _val(inp, "loadTons", basis["cap"])
    year = int(_jsround(_val(inp, "year", 2022)))
    cargo_type = "granel" if inp.get("cargoType") == "granel" else "sacos"
    if not (one > 0):
        raise ValueError("Distancia de ida inválida")
    if ton <= 0 or ton > basis["cap"] + 0.001:
        raise ValueError("Carga fuera de capacidad de referencia para " + str(type_))
    if year < 2000 or year > 2026:
        raise ValueError("Año de modelo fuera de 2000–2026")
    age = _ages(year)
    flat = _classification(one, inp.get("rows") or [])
    if not flat["valid"]:
        raise ValueError("Las clases viales introducidas superan la distancia de la ruta; ajusta los kilómetros.")
    led = flat["ledger"]
    share = lambda i: led[i] / one  # noqa: E731
    mountain = share("autopista_con") + share("pavimento_con") + share("terraceria_con")
    dirt = share("terraceria_sin") + share("terraceria_con")
    urban = share("urbano")
    pavement = share("pavimento_sin") + share("pavimento_con")
    rough_surface = urban + 0.45 * pavement + dirt

    asc_raw, desc_raw = inp.get("ascent", _UNDEF), inp.get("descent", _UNDEF)
    elevation_good = inp.get("elevationAvailable") is True and math.isfinite(_num(asc_raw)) and math.isfinite(_num(desc_raw))
    ascent = max(0.0, _num(asc_raw)) if elevation_good else 0.0
    descent = max(0.0, _num(desc_raw)) if elevation_good else 0.0
    hill = _val(inp, "hillSensitivity", 12)
    uphill_loaded = min(0.40, ascent / (one * 1000) * hill) if elevation_good else 0.0
    uphill_empty = min(0.40, descent / (one * 1000) * hill) if elevation_good else 0.0

    fuel_road = urban * _val(inp, "urbanFuelInc", 0.12) + pavement * _val(inp, "pavedFuelInc", 0.035) + dirt * _val(inp, "dirtFuelInc", 0.15)
    measured_wear = min(0.45, (ascent + descent) / (one * 1000) * _val(inp, "gradeWearSensitivity", 10)) if elevation_good else 0.0
    maintenance_road = measured_wear + urban * _val(inp, "urbanMaintInc", 0.05) + pavement * _val(inp, "pavedMaintInc", 0.06) + dirt * _val(inp, "dirtMaintInc", 0.27)
    tyre_road = measured_wear * 0.5 + urban * _val(inp, "urbanTireInc", 0.025) + pavement * _val(inp, "pavedTireInc", 0.045) + dirt * _val(inp, "dirtTireInc", 0.20)
    suspension_road = measured_wear * _val(inp, "suspGradeFactor", 1.2) + urban * _val(inp, "suspUrbanInc", 0.10) + pavement * _val(inp, "suspPavedInc", 0.12) + dirt * _val(inp, "suspDirtInc", 0.48)
    load_factor = 0.72 + 0.28 * _clamp(ton / basis["cap"], 0, 1)
    kml_loaded = _val(inp, "loadedKml", basis["kml"]) * age["consumption"]
    kml_empty = _val(inp, "emptyKml", basis["empty"]) * age["consumption"]
    laden_litres = one / max(0.1, kml_loaded) * load_factor * (1 + fuel_road + uphill_loaded)
    empty_litres = one / max(0.1, kml_empty) * (1 + fuel_road + uphill_empty)
    base_drive_h = max(0.2, _val(inp, "travelHours", one / 55)) * 2
    mountain_delay = min(0.25, (ascent + descent) / (one * 1000) * _val(inp, "gradeTimeSensitivity", 6)) if elevation_good else 0.0
    extra_drive_h = base_drive_h * (urban * _val(inp, "urbanDelay", 0.18) + mountain_delay + dirt * _val(inp, "dirtDelay", 0.23))
    handling = _val(inp, "handlingHours", 2)
    queue = _val(inp, "extraWaitHours", 0)
    journey_hours = base_drive_h + extra_drive_h + handling + queue
    idling_litres = _val(inp, "idleLph", basis["idle"]) * max(0, extra_drive_h + queue) * _val(inp, "idleEnabled", 1)
    diesel_litres = laden_litres + empty_litres + idling_litres

    diesel_price_input = _val(inp, "dieselPrice", math.nan)
    if not math.isfinite(diesel_price_input) or diesel_price_input < 10 or diesel_price_input > 60:
        raise ValueError("Precio estatal de diésel pendiente o inválido; espera el cálculo por estados o habilita el precio manual.")
    diesel_includes_iva = inp.get("dieselPriceIncludesIVA") is True
    diesel_iva = 0.16
    diesel_price = diesel_price_input / (1 + diesel_iva) if diesel_includes_iva else diesel_price_input
    fuel = diesel_litres * diesel_price
    distance = one * 2
    maintenance_rate = _val(inp, "maintenanceRate", basis["maintenance"]) * age["maintenance"]
    suspension_share = _clamp(_val(inp, "suspensionShare", 0.18), 0, 0.60)
    maintenance = distance * maintenance_rate * (1 - suspension_share) * (1 + maintenance_road)
    suspension = distance * maintenance_rate * suspension_share * (1 + suspension_road)
    tyre_count = _val(inp, "tyreCount", basis["tires"]["count"])
    tyre_price = _val(inp, "tyrePrice", basis["tires"]["price"])
    tyre_life = _val(inp, "tyreLife", basis["tires"]["life"])
    tyres = distance * (tyre_count * tyre_price / max(1, tyre_life)) * age["tires"] * (1 + tyre_road)
    lubricants = distance * _val(inp, "lubricantsRate", basis["lubes"])
    def_litres = diesel_litres * _val(inp, "defFraction", basis["def"])
    def_cost = def_litres * _val(inp, "defPrice", 14)

    tolls_one_way_input = _val(inp, "tollsOneWay", 0)
    tolls_includes_iva = inp.get("tollsPriceIncludesIVA") is True
    tolls_iva = 0.16
    tolls_one_way_net = tolls_one_way_input / (1 + tolls_iva) if tolls_includes_iva else tolls_one_way_input
    peajes = tolls_one_way_net * 2
    umbral = _val(inp, "viaticoUmbralHrs", 8)
    per_diem = _val(inp, "viaticoDia", 350) * max(1, math.ceil((journey_hours - umbral) / 24)) if journey_hours > umbral else 0
    operator_variable = inp.get("operatorMode") == "variable"
    misc = (_val(inp, "maniobras", 0) + per_diem + _val(inp, "viaticos", 0) + _val(inp, "custodia", 0) + _val(inp, "lavado", 0)
            + (distance * _val(inp, "operatorPerKm", 0) if operator_variable else 0))
    extra_variable = _val(inp, "riskExpense", 0)

    fixed = basis["fixed"]
    monthly = {
        "asset": _val(inp, "fixedAsset", fixed["asset"]),
        "operator": 0 if operator_variable else _val(inp, "fixedOperator", fixed["operator"]),
        "insurance": _val(inp, "fixedInsurance", fixed["insurance"]),
        "admin": _val(inp, "fixedAdmin", fixed["admin"]) * _val(inp, "carrierAdminFactor", _val(inp, "carrierFactor", 1)),
        "permit": _val(inp, "fixedPermit", fixed["permit"]),
        "gps": _val(inp, "fixedGps", fixed["gps"]),
        "patio": _val(inp, "fixedPatio", fixed["patio"]) * _val(inp, "carrierPatioFactor", 1),
        "workshopLabor": _val(inp, "fixedWorkshopLabor", 0),
    }
    monthly_total = sum(monthly.values())
    util = max(0.1, _val(inp, "carrierUtilizationFactor", 1))
    km_month = max(1, _val(inp, "kmMonth", basis["kmMonth"]) * util)
    monthly_available_hours = max(1, _val(inp, "daysMonth", 22) * _val(inp, "hoursPerDay", 10) * util)
    fixed_km = monthly_total * distance / km_month
    fixed_time = monthly_total * journey_hours / monthly_available_hours
    fixed_allocation = max(fixed_km, fixed_time)
    fixed_allocation_automatic = fixed_allocation
    fixed_driver = "Horas operativas" if fixed_time > fixed_km else "Kilómetros mensuales"

    variable = {"diesel": fuel, "maintenance": maintenance, "suspension": suspension, "tires": tyres, "lubricants": lubricants,
                "def": def_cost, "tolls": peajes, "serviceMisc": misc, "riskCost": extra_variable}
    automatic_variable = dict(variable)
    manual_applied: dict[str, float] = {}
    manual = inp.get("manualCosts") or {}
    for key, amount in (manual.items() if isinstance(manual, dict) else []):
        if amount is None or amount == "":
            continue
        override = _num(amount)
        if not math.isfinite(override) or override < 0:
            raise ValueError("Costo manual inválido: " + key)
        if key == "fixed":
            fixed_allocation = override
            manual_applied["fixed"] = override
        elif key in variable:
            variable[key] = override
            manual_applied[key] = override
    variable_total = sum(variable.values())
    cost = fixed_allocation + variable_total
    utility = _clamp(_val(inp, "utility", 0.08), 0, 0.50)
    profit = cost * utility
    tariff = cost + profit
    ref_tiers = references(tariff, inp.get("tierPremiums"))
    fees = {"fixed": fixed_allocation, **variable, "utility": profit}

    audit = {
        "manualApplied": manual_applied, "automaticVariable": automatic_variable, "fixedAllocationAutomatic": fixed_allocation_automatic,
        "oneKm": one, "roundKm": distance, "loadedKmlBase": _val(inp, "loadedKml", basis["kml"]), "emptyKmlBase": _val(inp, "emptyKml", basis["empty"]),
        "loadedKmlEffective": kml_loaded, "emptyKmlEffective": kml_empty,
        "ageFactors": dict(age), "loadFactor": load_factor, "fuelRoad": fuel_road, "uphillLoaded": uphill_loaded, "uphillEmpty": uphill_empty,
        "maintenanceRoad": maintenance_road, "tyreRoad": tyre_road, "suspensionRoad": suspension_road, "suspensionShare": suspension_share,
        "measuredWear": measured_wear, "mountainDelay": mountain_delay, "perDiem": per_diem, "roughSurface": rough_surface,
        "pavement": pavement, "urban": urban, "dirt": dirt,
        "baseDriveH": base_drive_h, "extraDriveH": extra_drive_h, "handling": handling, "queue": queue, "journeyHours": journey_hours,
        "mountain": mountain, "ascent": ascent, "descent": descent, "elevationGood": elevation_good,
        "dieselPrice": diesel_price, "dieselPriceInput": diesel_price_input, "dieselIncludesIVA": diesel_includes_iva, "dieselIVA": diesel_iva,
        "loadedLitres": laden_litres, "emptyLitres": empty_litres, "idlingLitres": idling_litres,
        "idleLph": _val(inp, "idleLph", basis["idle"]), "dieselLitres": diesel_litres,
        "maintenanceRateBase": _val(inp, "maintenanceRate", basis["maintenance"]), "maintenanceRateEffective": maintenance_rate,
        "tyreCount": tyre_count, "tyrePrice": tyre_price, "tyreLife": tyre_life,
        "lubeRate": _val(inp, "lubricantsRate", basis["lubes"]), "defFraction": _val(inp, "defFraction", basis["def"]), "defPrice": _val(inp, "defPrice", 14),
        "tollsOneWay": tolls_one_way_input, "tollsOneWayNet": tolls_one_way_net, "tollsIncludesIVA": tolls_includes_iva, "tollsIVA": tolls_iva,
        "tollStatus": inp.get("tollStatus") or "no-registrado", "kmMonth": km_month, "monthlyAvailableHours": monthly_available_hours,
        "operatorMode": inp.get("operatorMode") or "fijo",
        "utility": utility, "year": year, "loadTons": ton, "cargoType": cargo_type, "roadKm": dict(led),
        "params": {k: v for k, v in inp.items() if (isinstance(v, (int, float)) and not isinstance(v, bool)) or isinstance(v, str)},
    }
    warnings = []
    if flat["unknownKm"] > 0.1:
        warnings.append(f"{_fmt(_jsround(flat['unknownKm'] * 100) / 100)} km de la ida no tienen clase vial confirmada; se calcularon con condiciones base.")
    if not elevation_good:
        warnings.append("Sin perfil de elevación confiable: sin recargo de pendiente; no se inventa altimetría.")
    warnings.append("El regreso se aproxima con los mismos km, en sentido inverso y unidad vacía; no existe ruteo independiente de retorno ni casetas asimétricas.")
    if inp.get("tollStatus") in ("pending", "partial", "unavailable", "no-registrado"):
        warnings.append("Casetas: detección geográfica parcial o pendiente; el monto automático no representa el total garantizado de todos los tramos/concesiones.")
    if operator_variable and _val(inp, "operatorPerKm", 0) <= 0:
        warnings.append("Pago por km seleccionado: falta asignar remuneración variable al operador.")
    if manual_applied:
        warnings.append("La tarifa incluye rubros ajustados manualmente (" + ", ".join(manual_applied) + "). Los litros y factores técnicos muestran el valor automático; las cifras manuales prevalecen para cotizar.")
    warnings.append("Modelo GC-FIS independiente de índices GeoRisk; las clases sin evidencia OSM se costean como base y reducen la confianza del cálculo.")
    warnings.append("Rendimientos y ajustes por año, carga y terreno son supuestos preliminares; fabricante/modelo no asigna una ficha técnica sin medición y deben calibrarse con litros y kilometraje reales de la flotilla.")

    return {
        "type": type_, "year": year, "age": age["period"], "cargoType": cargo_type, "kmOneWay": one, "kmTotal": distance, "loadTons": ton,
        "journeyHours": journey_hours, "monthlyTotal": monthly_total, "monthly": monthly, "fixedAllocation": fixed_allocation,
        "fixedKm": fixed_km, "fixedTime": fixed_time, "fixedDriver": fixed_driver, "variable": variable, "variableTotal": variable_total,
        "cost": cost, "utility": utility, "profit": profit, "tariff": tariff, "refTiers": ref_tiers,
        "carrierAdminFactor": _val(inp, "carrierAdminFactor", _val(inp, "carrierFactor", 1)),
        "carrierPatioFactor": _val(inp, "carrierPatioFactor", 1), "carrierUtilizationFactor": _val(inp, "carrierUtilizationFactor", 1),
        "fees": fees, "dieselLitres": diesel_litres, "loadedLitres": laden_litres, "emptyLitres": empty_litres, "idlingLitres": idling_litres,
        "defLitres": def_litres, "ascent": ascent, "descent": descent, "uphillLoaded": uphill_loaded, "uphillEmpty": uphill_empty,
        "mountainShare": mountain, "urbanShare": urban, "dirtShare": dirt, "classifiedKm": flat["known"], "unclassifiedKm": flat["unknownKm"],
        "monthlyAvailableHours": monthly_available_hours, "kmMonth": km_month, "warnings": warnings, "audit": audit,
    }
