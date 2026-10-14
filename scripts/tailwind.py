"""
Compila el CSS del sitio con la CLI standalone de Tailwind (sin Node).

Uso:
    python scripts/tailwind.py install   # descarga y verifica el binario fijado
    python scripts/tailwind.py build     # genera static/css/app.css (minificado)
    python scripts/tailwind.py watch     # recompila al cambiar plantillas o CSS

El binario se guarda en `.tools/` (ignorado por Git) y solo se acepta si su
SHA-256 coincide con el publicado por Tailwind para la versión fijada.
"""
import hashlib
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

VERSION = "v4.3.3"
# sha256sums.txt oficial de la release v4.3.3.
SHA256 = {
    "windows-x64.exe": "e0e260ce048014e9268f6237ff18f8ccf02cef521cbd0ae04e82c2cdf7aa3955",
    "linux-x64": "dc61b3ac6b8c9ca874c0cc4c57b2409791a64c5540404ca5f5367360babc313a",
    "linux-arm64": "55fd0b241214eff3de1e8ee4f22796662f2d2e7a49bcfca7477cfd0bac398195",
    "macos-x64": "7922e0953f2110c05976e3bf58f14e643d90427575e766b7d433f5f80cbee7e1",
    "macos-arm64": "cdf646702987a743464dff4d9c60fd4480d1c1e73dd819a9a67f1078815dce9d",
}

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / ".tools"
INPUT = ROOT / "assets" / "css" / "input.css"
OUTPUT = ROOT / "static" / "css" / "app.css"


def _platform_key():
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system())
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    key = f"{system}-{arch}" + (".exe" if system == "windows" else "")
    if key not in SHA256:
        sys.exit(f"Plataforma no soportada por este script: {platform.system()} {machine}")
    return key


def _binary_path():
    return TOOLS / ("tailwindcss.exe" if platform.system() == "Windows" else "tailwindcss")


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install():
    key = _platform_key()
    binary = _binary_path()
    if binary.exists() and _sha256(binary) == SHA256[key]:
        print(f"Tailwind {VERSION} ya instalado en {binary.relative_to(ROOT)}")
        return binary
    TOOLS.mkdir(exist_ok=True)
    url = f"https://github.com/tailwindlabs/tailwindcss/releases/download/{VERSION}/tailwindcss-{key}"
    tmp = binary.with_suffix(".download")
    print(f"Descargando {url}")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 - URL fija de GitHub releases
    if _sha256(tmp) != SHA256[key]:
        tmp.unlink()
        sys.exit("El checksum del binario descargado no coincide. Se ha descartado.")
    tmp.replace(binary)
    binary.chmod(0o755)
    print(f"Tailwind {VERSION} verificado e instalado en {binary.relative_to(ROOT)}")
    return binary


def run(*extra):
    binary = install()
    cmd = [str(binary), "-i", str(INPUT), "-o", str(OUTPUT), *extra]
    return subprocess.call(cmd, cwd=ROOT)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "build"
    if action == "install":
        install()
    elif action == "build":
        sys.exit(run("--minify"))
    elif action == "watch":
        sys.exit(run("--watch"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
