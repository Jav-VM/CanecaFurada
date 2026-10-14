"""
Emails transaccionales de cuentas.

Los enlaces se construyen con `SITE_BASE_URL`, nunca con la cabecera Host de la
petición. Los fallos de envío se registran sin destinatario, token ni enlace.
Ninguna de estas funciones envía comunicaciones promocionales.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def _send(*, to, template, context):
    context = {"site_base_url": settings.SITE_BASE_URL, **context}
    subject = render_to_string(f"emails/{template}_subject.txt", context).strip()
    body = render_to_string(f"emails/{template}_body.txt", context)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
    except Exception as exc:  # noqa: BLE001 - un fallo del SMTP no debe romper el flujo
        logger.error("No se pudo enviar el email '%s' (%s).", template, type(exc).__name__)
        return False
    return True


def verification_url(raw_token):
    return settings.SITE_BASE_URL + reverse("accounts:verify_email", args=[raw_token])


def send_verification_email(*, to, first_name, raw_token, ttl_hours, is_email_change):
    return _send(
        to=to,
        template="email_change" if is_email_change else "verify_email",
        context={
            "first_name": first_name,
            "verification_url": verification_url(raw_token),
            "ttl_hours": ttl_hours,
        },
    )


def send_email_changed_notice(*, to, first_name):
    """Aviso de seguridad a la dirección anterior tras un cambio de email."""
    return _send(to=to, template="email_changed_notice", context={"first_name": first_name})


def send_existing_account_notice(*, to):
    """Se envía cuando alguien intenta registrarse con un email ya registrado."""
    return _send(
        to=to,
        template="existing_account",
        context={"password_reset_url": settings.SITE_BASE_URL + reverse("accounts:password_reset")},
    )
