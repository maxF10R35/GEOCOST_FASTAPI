"""Paridad del motor Python contra el motor JavaScript (casos generados con tools/generar_golden.js)."""
import json
import math
from pathlib import Path

import pytest

from app.services.cost_engine import quote

CASOS = json.loads((Path(__file__).parent / "golden" / "quote_cases.json").read_text(encoding="utf-8"))


def _igual(a, b, ruta=""):
    """Compara estructuras; números con tolerancia relativa de 1e-9 (JSON de JS no distingue int/float)."""
    if isinstance(b, dict):
        assert isinstance(a, dict), f"{ruta}: se esperaba objeto"
        assert set(a) == set(b), f"{ruta}: claves distintas {set(a) ^ set(b)}"
        for k in b:
            _igual(a[k], b[k], f"{ruta}.{k}")
    elif isinstance(b, list):
        assert isinstance(a, list) and len(a) == len(b), f"{ruta}: listas de distinto tamaño"
        for i, (x, y) in enumerate(zip(a, b)):
            _igual(x, y, f"{ruta}[{i}]")
    elif isinstance(b, bool) or b is None or isinstance(b, str):
        assert a == b, f"{ruta}: {a!r} != {b!r}"
    else:
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{ruta}: {a} != {b}"


@pytest.mark.parametrize("caso", CASOS, ids=[c["name"] for c in CASOS])
def test_paridad(caso):
    esperado = caso["expected"]
    if "error" in esperado and len(esperado) == 1:
        with pytest.raises(ValueError) as e:
            quote(caso["input"])
        assert str(e.value) == esperado["error"]
    else:
        _igual(quote(caso["input"]), esperado)


def test_hay_cobertura_suficiente():
    ok = [c for c in CASOS if "error" not in c["expected"]]
    assert len(CASOS) >= 250 and len(ok) >= 230
    assert any(c["expected"]["audit"]["manualApplied"] for c in ok)
    assert any(c["expected"]["audit"]["elevationGood"] for c in ok)
    assert any(c["expected"]["audit"]["operatorMode"] == "variable" for c in ok)
    assert any(c["expected"]["audit"]["dieselIncludesIVA"] for c in ok)
