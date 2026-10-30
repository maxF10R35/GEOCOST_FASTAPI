import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
CASOS = {c["name"]: c for c in json.loads((Path(__file__).parent / "golden" / "quote_cases.json").read_text(encoding="utf-8"))}


def test_calcular_coincide_con_el_motor_js():
    caso = CASOS["referencia_rabon_53km"]
    r = client.post("/api/v1/cotizaciones/calcular", json=caso["input"])
    assert r.status_code == 200
    d = r.json()
    assert abs(d["tariff"] - caso["expected"]["tariff"]) < 1e-6
    assert [t["id"] for t in d["refTiers"]] == ["C", "CP", "B", "BP", "SPOT"]


def test_calcular_rechaza_entradas_invalidas_con_422():
    r = client.post("/api/v1/cotizaciones/calcular", json=CASOS["error_sobrecarga"]["input"])
    assert r.status_code == 422
    assert "capacidad" in r.json()["detail"]


def test_parametros_vehiculos():
    r = client.get("/api/v1/parametros/vehiculos")
    assert r.status_code == 200
    d = r.json()
    assert set(d["vehiculos"]) == {"Camioneta", "Rabón", "Torton", "Tráiler", "Full"}
    assert len(d["clasesViales"]) == 7 and len(d["referencias"]) == 5


def test_health_sigue_funcionando():
    assert client.get("/api/health").status_code == 200
