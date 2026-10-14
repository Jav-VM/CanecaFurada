"""
Enlace de baja de las comunicaciones promocionales.

Cada email o SMS promocional lleva un enlace para retirar el consentimiento
sin iniciar sesión. El token lo firma Django (`django.core.signing`, con la
`SECRET_KEY` y una sal propia): contiene solo el `public_id` del cliente y el
canal, no se puede falsificar y solo sirve para darse de baja. Caduca a los
`NOTIFICATIONS_UNSUBSCRIBE_MAX_AGE_DAYS` días; después, la baja se hace desde
el perfil. La página pide confirmar con un botón (POST) para que los
antivirus o vistas previas que abren enlaces no den de baja a nadie.
"""
import uuid

from django.conf import settings
from django.core import signing
from django.urls import reverse

from apps.accounts.models import User

from .models import Channel

SALT = "apps.notifications.unsubscribe"


def make_token(user, channel):
    return signing.dumps({"u": str(user.public_id), "c": channel}, salt=SALT, compress=True)


def unsubscribe_url(user, channel):
    return settings.SITE_BASE_URL + reverse("notifications:unsubscribe", args=[make_token(user, channel)])


def read_token(token):
    """Devuelve `(usuario, canal)` o `None` si el token no es válido, ha caducado o el cliente no existe."""
    if not token or len(token) > 300:
        return None
    max_age = settings.NOTIFICATIONS_UNSUBSCRIBE_MAX_AGE_DAYS * 24 * 60 * 60
    try:
        data = signing.loads(token, salt=SALT, max_age=max_age)
    except signing.BadSignature:  # incluye SignatureExpired
        return None
    if not isinstance(data, dict) or data.get("c") not in Channel.values:
        return None
    try:
        public_id = uuid.UUID(str(data.get("u")))
    except ValueError:
        return None
    user = User.objects.filter(public_id=public_id, role=User.Role.CUSTOMER).first()
    if user is None:
        return None
    return user, data["c"]
