"""
Traducciones de la interfaz (Fase 15). Necesita GNU gettext (msgfmt, xgettext).

Uso:
    python scripts/i18n.py make      # actualiza locale/gl (y locale/es) con las cadenas del código
    python scripts/i18n.py compile   # genera los .mo (no se versionan)
    python scripts/i18n.py check     # falla si los .po no están al día, están incompletos o tienen errores

El castellano es el idioma fuente (los msgid). Aun así hace falta un catálogo
`es` en el que cada msgstr repite su msgid (lo genera `msgen`): sin él, Django
usa el gallego (`LANGUAGE_CODE`) como respaldo de toda cadena que no encuentra
en castellano, y la bandera de España no cambiaría nada. Las líneas no se parten
(`--no-wrap`) ni llevan referencias al código (`--no-location`), para que el
resultado no dependa de la versión de gettext ni cambie con cada edición.
Ver docs/fase-15-idioma-gallego.md.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO = ROOT / "locale" / "gl" / "LC_MESSAGES" / "django.po"
PO_ES = ROOT / "locale" / "es" / "LC_MESSAGES" / "django.po"
IGNORE = ("staticfiles", "media", "tests", "pruebas_dev", "docs", "scripts", "apps/demo", ".venv", ".tools")
MAKE = [
    sys.executable, "manage.py", "makemessages", "-l", "gl", "-e", "html,txt,py",
    "--no-location", "--no-wrap", "--no-obsolete", *[f"--ignore={d}" for d in IGNORE],
]


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, check=True)


def make():
    run(MAKE)
    make_spanish()


ES_HEADER = """# Catálogo castellano de Caneca Furada: cada msgstr repite su msgid.
# Generado por `python scripts/i18n.py make`; no se edita a mano.
#
"""
STRING = r'(?:"(?:[^"\\]|\\.)*"\n)+'  # una cadena del .po, con sus líneas de continuación


def make_spanish():
    """Catálogo castellano idéntico al texto fuente (msgstr = msgid)."""
    header, *entries = PO.read_text(encoding="utf-8").split("\n\n")
    header = re.sub(r"\A(#.*\n)+", ES_HEADER, header)
    header = header.replace('"Language-Team: Galego\\n"', '"Language-Team: Castellano\\n"')
    header = header.replace('"Language: gl\\n"', '"Language: es\\n"')
    copied = []
    for entry in entries:
        entry = entry.strip("\n") + "\n"
        singular = re.search(rf"^msgid ({STRING})", entry, re.M)
        plural = re.search(rf"^msgid_plural ({STRING})", entry, re.M)
        entry = entry[: re.search(r"^msgstr", entry, re.M).start()]
        if plural:
            entry += f"msgstr[0] {singular.group(1)}msgstr[1] {plural.group(1)}"
        else:
            entry += f"msgstr {singular.group(1)}"
        copied.append(entry.rstrip("\n"))
    PO_ES.parent.mkdir(parents=True, exist_ok=True)
    PO_ES.write_text("\n\n".join([header.rstrip("\n"), *copied]) + "\n", encoding="utf-8", newline="\n")


def compile_():
    run([sys.executable, "manage.py", "compilemessages", "--ignore=.venv", "--ignore=.tools"])


def check():
    before = {po: po.read_text(encoding="utf-8") if po.exists() else "" for po in (PO, PO_ES)}
    make()
    after = PO.read_text(encoding="utf-8")
    strip = lambda s: re.sub(r'^"POT-Creation-Date: .*\n', "", s, flags=re.M)  # noqa: E731
    errors = []
    for po, text in before.items():
        if strip(text) != strip(po.read_text(encoding="utf-8")):
            po.write_text(text, encoding="utf-8", newline="\n")
            errors.append(f"{po.relative_to(ROOT).as_posix()} no está al día: ejecuta `python scripts/i18n.py make` y traduce las cadenas nuevas.")
    if re.search(r"^#, .*fuzzy", after, re.M):
        errors.append("Hay traducciones marcadas como dudosas (fuzzy).")
    blocks = [b for b in re.split(r"\n\s*\n", after) if "msgid" in b][1:]
    # Vacía = `msgstr ""` sin líneas de continuación detrás.
    empty = [b for b in blocks if re.search(r'^msgstr(\[\d\])? ""\n(?!")', b + "\n", re.M)]
    if empty:
        errors.append(f"Hay {len(empty)} cadenas sin traducir.")
    for po in (PO, PO_ES):
        result = subprocess.run(["msgfmt", "--check", "-o", "-", str(po)], cwd=ROOT, capture_output=True)
        if result.returncode:
            errors.append(f"msgfmt --check ha fallado en {po.relative_to(ROOT).as_posix()}:\n" + result.stderr.decode(errors="replace"))
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("Traducciones al día y completas.")


if __name__ == "__main__":
    commands = {"make": make, "compile": compile_, "check": check}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
