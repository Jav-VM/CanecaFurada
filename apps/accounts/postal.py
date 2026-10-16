"""
Provincia y localidad a partir del código postal.

- Provincia: en España los dos primeros dígitos del CP identifican la provincia
  (tabla fija con los nombres oficiales del INE).
- Localidad: municipio o municipios de cada CP según GeoNames (CC BY 4.0),
  generado con `scripts/postal_codes.py` en `data/postal_codes_es.json`.

Solo hay datos de España; para otros países todo devuelve vacío y la localidad
se escribe a mano. Lo usan el modelo, los formularios, la web y la API.
"""
import functools
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .validators import normalize_text

DATA_FILE = Path(__file__).resolve().parent / "data" / "postal_codes_es.json"
SOURCE_NOTE = "GeoNames (CC BY 4.0)"

PROVINCES_ES = {
    "01": "Araba/Álava", "02": "Albacete", "03": "Alicante/Alacant", "04": "Almería", "05": "Ávila",
    "06": "Badajoz", "07": "Illes Balears", "08": "Barcelona", "09": "Burgos", "10": "Cáceres",
    "11": "Cádiz", "12": "Castellón/Castelló", "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña",
    "16": "Cuenca", "17": "Girona", "18": "Granada", "19": "Guadalajara", "20": "Gipuzkoa",
    "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León", "25": "Lleida",
    "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga", "30": "Murcia",
    "31": "Navarra", "32": "Ourense", "33": "Asturias", "34": "Palencia", "35": "Las Palmas",
    "36": "Pontevedra", "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria", "40": "Segovia",
    "41": "Sevilla", "42": "Soria", "43": "Tarragona", "44": "Teruel", "45": "Toledo",
    "46": "Valencia/València", "47": "Valladolid", "48": "Bizkaia", "49": "Zamora", "50": "Zaragoza",
    "51": "Ceuta", "52": "Melilla",
}


@functools.lru_cache(maxsize=1)
def _localities_es():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))["localities"]


def province_for(country, postal_code):
    """Provincia deducida del CP, o "" si el país no es España o el CP no encaja."""
    if country != "ES" or not postal_code:
        return ""
    return PROVINCES_ES.get(postal_code[:2], "")


def localities_for(country, postal_code):
    """Localidades conocidas para el CP (lista vacía si no hay datos)."""
    if country != "ES" or not postal_code:
        return []
    return list(_localities_es().get(postal_code, ()))


def canonical_locality(country, postal_code, value):
    """
    Localidad validada contra los datos del CP.

    Si hay datos, el valor debe ser uno de ellos (sin distinguir mayúsculas) y se
    devuelve con su nombre canónico; vacío es un error. Sin datos, se devuelve
    el texto normalizado tal cual (puede ser vacío).
    """
    value = normalize_text(value)
    options = localities_for(country, postal_code)
    if not options:
        return value
    if not value:
        raise ValidationError(_("Elige tu localidad."), code="locality_required")
    for option in options:
        if option.casefold() == value.casefold():
            return option
    raise ValidationError(_("Elige una localidad de la lista para este código postal."), code="invalid_locality")
