"""Catálogo canónico de estados (clave INEGI) y normalización de nombres.
Las fuentes escriben el mismo estado de formas distintas (ZT: «Edo de Mexico», diésel: «Estado de México»,
referencias: «Baja California S»); todo se reconcilia aquí a la clave de 2 dígitos."""
import re
import unicodedata

ESTADOS = [
    ("01", "Aguascalientes", []),
    ("02", "Baja California", []),
    ("03", "Baja California Sur", ["Baja California S"]),
    ("04", "Campeche", []),
    ("05", "Coahuila de Zaragoza", ["Coahuila"]),
    ("06", "Colima", []),
    ("07", "Chiapas", []),
    ("08", "Chihuahua", []),
    ("09", "Ciudad de México", ["Distrito Federal", "CDMX"]),
    ("10", "Durango", []),
    ("11", "Guanajuato", ["Guanajuato-ZT.KML"]),
    ("12", "Guerrero", []),
    ("13", "Hidalgo", []),
    ("14", "Jalisco", []),
    ("15", "México", ["Estado de México", "Edo de Mexico", "Edo. de México"]),
    ("16", "Michoacán de Ocampo", ["Michoacán"]),
    ("17", "Morelos", []),
    ("18", "Nayarit", []),
    ("19", "Nuevo León", []),
    ("20", "Oaxaca", []),
    ("21", "Puebla", []),
    ("22", "Querétaro", []),
    ("23", "Quintana Roo", []),
    ("24", "San Luis Potosí", []),
    ("25", "Sinaloa", []),
    ("26", "Sonora", []),
    ("27", "Tabasco", []),
    ("28", "Tamaulipas", []),
    ("29", "Tlaxcala", []),
    ("30", "Veracruz de Ignacio de la Llave", ["Veracruz", "Veracruz de Ignacio"]),
    ("31", "Yucatán", []),
    ("32", "Zacatecas", []),
]


def norm(texto) -> str:
    """minúsculas, sin acentos y solo letras: «Edo. de México» -> «edodemexico»"""
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    return re.sub(r"[^a-z]", "", s.encode("ascii", "ignore").decode())


ALIAS: dict[str, str] = {}
for clave, nombre, extras in ESTADOS:
    for n in [nombre, *extras]:
        k = norm(n)
        assert ALIAS.get(k, clave) == clave, f"alias ambiguo: {n}"
        ALIAS[k] = clave


def clave_estado(texto):
    """Clave INEGI o None si el nombre no se reconoce."""
    return ALIAS.get(norm(texto))
