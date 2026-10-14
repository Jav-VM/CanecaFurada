"""
Formularios de canjes. Solo convierten la entrada: las reglas (saldo,
disponibilidad, permisos, códigos) las aplica `services`, que es lo que usará
también la API.
"""
from django import forms


class RedeemForm(forms.Form):
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=36)


class RedemptionCodeForm(forms.Form):
    code = forms.CharField(
        label="Código del canje",
        max_length=100,
        help_text="Se rellena al escanear el QR del canje. Si la cámara no funciona, escribe el código (p. ej. ABCD-EFGH-JKMN).",
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}
        ),
    )


class ValidateRedemptionForm(forms.Form):
    code = forms.CharField(widget=forms.HiddenInput, max_length=100)
