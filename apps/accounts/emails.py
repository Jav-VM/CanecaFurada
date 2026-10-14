"""
Emails transaccionales de cuentas.

Desde la Fase 10 se envían a través de `apps.notifications.services.send_immediately`,
que deja constancia de cada envío (enviado o fallido) sin guardar el
destinatario, el enlace ni el token. Los enlaces se construyen con
`SITE_BASE_URL`, nunca con la cabecera Host de la petición. Ninguna de estas
funciones envía comunicaciones promocionales.
"""
from django.conf import settings
from django.urls import reverse

from apps.notifications import services as notifications
from apps.notifications.models import Notification

Kind = Notification.Kind


def _send(*, kind, user, to, template, context):
    return notifications.send_immediately(
        kind=kind,
        recipient=user,
        to=to,
        subject_template=f"emails/{template}_subject.txt",
        body_template=f"emails/{template}_body.txt",
        context=context,
    )


def verification_url(raw_token):
    return settings.SITE_BASE_URL + reverse("accounts:verify_email", args=[raw_token])


def send_verification_email(*, user, to, first_name, raw_token, ttl_hours, is_email_change):
    return _send(
        kind=Kind.EMAIL_CHANGE if is_email_change else Kind.EMAIL_VERIFICATION,
        user=user,
        to=to,
        template="email_change" if is_email_change else "verify_email",
        context={
            "first_name": first_name,
            "verification_url": verification_url(raw_token),
            "ttl_hours": ttl_hours,
        },
    )


def send_email_changed_notice(*, user, to, first_name):
    """Aviso de seguridad a la dirección anterior tras un cambio de email."""
    return _send(
        kind=Kind.EMAIL_CHANGED_NOTICE,
        user=user,
        to=to,
        template="email_changed_notice",
        context={"first_name": first_name},
    )


def send_existing_account_notice(*, user, to):
    """Se envía cuando alguien intenta registrarse con un email ya registrado."""
    return _send(
        kind=Kind.EXISTING_ACCOUNT,
        user=user,
        to=to,
        template="existing_account",
        context={"password_reset_url": settings.SITE_BASE_URL + reverse("accounts:password_reset")},
    )


def send_password_reset(*, user, to, subject_template, body_template, context):
    """Recuperación de la cuenta (formulario nativo de Django, ver `forms.NotifyingPasswordResetForm`)."""
    return notifications.send_immediately(
        kind=Kind.PASSWORD_RESET,
        recipient=user,
        to=to,
        subject_template=subject_template,
        body_template=body_template,
        context=context,
    )
