"""
Formularios de reservas del cliente. Solo convierten la entrada: fechas
permitidas, aforo, límites y estados los valida `services`, que es lo que
usará también la API.
"""
import datetime

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import Reservation


class _ReservationBaseForm(forms.Form):
    party_size = forms.IntegerField(
        label="Personas",
        min_value=1,
        max_value=Reservation.MAX_PARTY_SIZE,
        initial=2,
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
    )
    notes = forms.CharField(
        label="Comentarios",
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Opcional. Solo lo verá el local. No incluyas datos de salud ni otros datos sensibles.",
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=36)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        maximum = settings.EVENTS_RESERVATION_MAX_PARTY_SIZE
        self.fields["party_size"].max_value = maximum
        self.fields["party_size"].widget.attrs["max"] = maximum
        self.fields["party_size"].help_text = f"Entre 1 y {maximum}. Para grupos mayores, contacta con el local."

    def service_kwargs(self):
        data = self.cleaned_data
        return {"party_size": data["party_size"], "notes": data["notes"], "idempotency_key": data["idempotency_key"]}


class TableReservationForm(_ReservationBaseForm):
    date = forms.DateField(label="Día", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(label="Hora", widget=forms.TimeInput(attrs={"type": "time", "step": 900}))

    field_order = ["date", "time", "party_size", "notes", "idempotency_key"]

    def service_kwargs(self):
        kwargs = super().service_kwargs()
        moment = datetime.datetime.combine(self.cleaned_data["date"], self.cleaned_data["time"])
        kwargs["requested_for"] = timezone.make_aware(moment)
        return kwargs


class EventReservationForm(_ReservationBaseForm):
    pass


class CancelReservationForm(forms.Form):
    """Sin campos: solo exige POST con CSRF."""
