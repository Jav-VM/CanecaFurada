"""
Formularios del panel de compras. Solo convierten la entrada: las reglas
(importe, QR, permisos, idempotencia) las aplica `services`, que es lo que
usará también la API.
"""
from django import forms

from . import services


class IdentifyForm(forms.Form):
    code = forms.CharField(
        label="Código del cliente",
        max_length=100,
        help_text="Se rellena al escanear el QR. Si la cámara no funciona, escribe el código que aparece bajo el QR.",
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}
        ),
    )


class PurchaseForm(forms.Form):
    code = forms.CharField(widget=forms.HiddenInput, max_length=100)
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=36)
    amount = forms.CharField(
        label="Importe (€)",
        max_length=12,
        help_text="Importe total pagado, por ejemplo 12,50.",
        widget=forms.TextInput(
            # Letra grande: se teclea en barra, a menudo en un móvil o tablet.
            attrs={"inputmode": "decimal", "autocomplete": "off", "class": "text-2xl font-bold"}
        ),
    )

    def clean_amount(self):
        return services.parse_amount(self.cleaned_data["amount"])
