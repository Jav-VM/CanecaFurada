"""QR en pantalla: siempre QR normal, nunca Micro QR (la cámara del panel no lee Micro QR)."""
import re
from urllib.parse import unquote

import segno
from django.test import SimpleTestCase

from apps.core.qr import qr_data_uri, qr_symbol
from apps.loyalty import services as loyalty
from apps.rewards import codes

REDEMPTION_PAYLOAD = codes.qr_payload("ABCDEFGHJKMN")


def modules_in(data_uri):
    """Módulos por lado del SVG (`scale=8`, `border=4`), leídos de su ancho."""
    width = int(re.search(r"width=['\"](\d+)['\"]", unquote(data_uri)).group(1))
    return width // 8 - 2 * 4


class QrTests(SimpleTestCase):
    def test_short_redemption_payload_was_a_micro_qr_with_segno_make(self):
        # La causa del fallo: con `segno.make` el QR del canje salía como Micro QR (M4).
        self.assertTrue(segno.make(REDEMPTION_PAYLOAD, error="m").is_micro)

    def test_qr_symbol_is_always_a_regular_qr(self):
        for payload in (REDEMPTION_PAYLOAD, loyalty.qr_payload("A" * 32), "x"):
            with self.subTest(payload=payload):
                symbol = qr_symbol(payload)
                self.assertFalse(symbol.is_micro)
                # Al menos el nivel M pedido (segno lo sube si cabe sin cambiar de versión).
                self.assertIn(symbol.error, ("M", "Q", "H"))

    def test_data_uri_is_a_regular_qr_svg(self):
        uri = qr_data_uri(REDEMPTION_PAYLOAD)
        self.assertTrue(uri.startswith("data:image/svg+xml"))
        # Versión 1 de QR normal: 21 módulos por lado (un Micro QR M4 tiene 17).
        self.assertEqual(modules_in(uri), 21)
