"""
Genera la tabla código postal → localidad (municipio) de España a partir de GeoNames.

Uso:
    python scripts/postal_codes.py build   # descarga ES.zip y regenera el JSON

Fuente: GeoNames (https://www.geonames.org/), licencia CC BY 4.0. Hay que citarla
allí donde se muestren los datos. GeoNames no publica checksums y el fichero se
actualiza, así que no se fija un hash: el JSON generado está versionado (los
cambios se revisan en el diff) y lleva la fecha y el SHA-256 del zip usado.
Solo se ejecuta para actualizar los datos; la aplicación nunca descarga nada.
"""
import datetime
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.geonames.org/export/zip/ES.zip"
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "apps" / "accounts" / "data" / "postal_codes_es.json"


def build():
    print(f"Descargando {URL}")
    with urllib.request.urlopen(URL, timeout=60) as response:  # noqa: S310 - URL fija de GeoNames
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        text = archive.read("ES.txt").decode("utf-8")

    # Columnas: país, CP, lugar, comunidad, cód., provincia, cód., municipio, cód., lat, lon, precisión.
    # Se usa el municipio: el «lugar» baja a parroquias y calles («Suso (Arteixo)»), demasiado
    # detalle para elegir y para agrupar zonas. Casi todos los CP tienen un único municipio; los
    # que no traen ninguno (apartados, organismos) quedan fuera y la localidad será texto libre.
    localities = {}
    for line in text.splitlines():
        columns = line.split("\t")
        if len(columns) < 8 or columns[0] != "ES":
            continue
        postal_code, name = columns[1].strip(), " ".join(columns[7].split())
        if len(postal_code) == 5 and postal_code.isdigit() and name:
            localities.setdefault(postal_code, set()).add(name)

    data = {
        "source": "GeoNames (https://www.geonames.org/), CC BY 4.0",
        "url": URL,
        "downloaded": datetime.date.today().isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "localities": {code: sorted(names) for code, names in sorted(localities.items())},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    total = sum(len(names) for names in localities.values())
    print(f"{len(localities)} códigos postales, {total} municipios → {OUTPUT.relative_to(ROOT)}")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"
    if action == "build":
        build()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
