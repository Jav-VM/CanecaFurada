"""
Eventos y reservas en el admin (solo propietarios).

- **Eventos:** se guardan con `services.save_event` (validación y auditoría).
  No se borran: se archivan. La gestión diaria está en el dashboard.
- **Reservas:** solo lectura y sin datos de contacto ni notas; los cambios de
  estado se hacen en el dashboard, que valida las transiciones.
"""
from django.contrib import admin

from apps.accounts.permissions import is_owner

from . import services
from .models import Event, Reservation


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "status", "accepts_reservations", "capacity", "is_featured")
    list_filter = ("status", "accepts_reservations")
    search_fields = ("title",)
    readonly_fields = ("public_id", "status", "published_at")
    fields = (
        "title",
        "summary",
        "description",
        "starts_at",
        "ends_at",
        "image",
        "is_featured",
        "accepts_reservations",
        "capacity",
        "status",
        "published_at",
        "public_id",
    )

    def has_module_permission(self, request):
        return is_owner(request.user)

    def has_view_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_add_permission(self, request):
        return is_owner(request.user)

    def has_change_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        data = {name: form.cleaned_data[name] for name in services.EVENT_FIELDS if name in form.cleaned_data}
        if data.get("image") is False:
            data["image"] = ""
        target = obj if change else Event()
        saved = services.save_event(actor=request.user, event=target, data=data)
        obj.pk, obj.public_id = saved.pk, saved.public_id


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("public_id", "requested_for", "party_size", "status", "event")
    list_filter = ("status",)
    fields = ("public_id", "event", "requested_for", "party_size", "status", "status_changed_at", "created_at")
    readonly_fields = fields

    def has_module_permission(self, request):
        return is_owner(request.user)

    def has_view_permission(self, request, obj=None):
        return is_owner(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
