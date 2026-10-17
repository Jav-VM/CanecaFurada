"""
Imágenes QR que se enseñan en pantalla (QR personal y QR de canje).

Siempre un QR normal (`segno.make_qr`), nunca un Micro QR: `segno.make` elige
Micro QR si el contenido cabe, y ni el lector nativo del navegador
(`BarcodeDetector`, formato `qr_code`) ni jsQR lo leen. Le pasaba al QR de los
canjes (`CFR1:` + 12 caracteres). Se genera aquí como SVG en data URI: sin
peticiones a terceros ni HTML sin escapar.
"""
import segno


def qr_symbol(payload):
    return segno.make_qr(payload, error="m")


def qr_data_uri(payload):
    return qr_symbol(payload).svg_data_uri(scale=8, border=4, dark="#080808", light="#ffffff")
