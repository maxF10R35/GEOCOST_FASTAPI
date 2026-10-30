from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.services import cost_engine

router = APIRouter(tags=["cotizaciones"])


@router.post("/cotizaciones/calcular")
def calcular(payload: dict[str, Any] = Body(...)):
    """Calcula la tarifa con el motor de costos. Mismo contrato (claves camelCase) que `GCIMT.quote` del sistema JS."""
    try:
        return cost_engine.quote(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/parametros/vehiculos")
def parametros_vehiculos():
    """Valores base por unidad, perfiles de transportista, niveles de referencia y clases viales."""
    return {
        "vehiculos": cost_engine.DEFS,
        "perfilesTransportista": cost_engine.CARRIER_PROFILES,
        "referencias": cost_engine.TIER_DEFAULTS,
        "clasesViales": cost_engine.CLASSES,
    }
