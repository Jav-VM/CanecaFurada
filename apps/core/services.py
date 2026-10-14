from .models import AuditEvent


def record_audit_event(*, action, actor=None, target=None, metadata=None):
    """
    Registra un evento de auditoría.

    `target` es cualquier objeto con `public_id`. `metadata` no debe incluir
    datos personales ni secretos.
    """
    return AuditEvent.objects.create(
        action=action,
        actor=actor,
        target_public_id=getattr(target, "public_id", None),
        metadata=metadata or {},
    )
