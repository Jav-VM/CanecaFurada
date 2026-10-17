"""
Borradores base de los textos legales (Fase 25).

Describen lo que hace de verdad la web (datos que pide, para qué, cookies,
reglas del programa con los valores reales de la configuración). No inventan
datos del negocio: lo que falta se muestra como «[pendiente de publicar]» o
«[pendiente: …]». Son un punto de partida para el asesor legal, no un texto
definitivo, y lo indican en la primera línea. Solo en castellano: lo que publica
el propietario no se traduce (Fase 15).
"""
from django.conf import settings

PENDING = "[pendiente de publicar]"
DRAFT_NOTICE = "BORRADOR PENDIENTE DE REVISIÓN LEGAL. Este texto es una base generada a partir del funcionamiento de la web; el titular debe revisarlo con su asesor y publicarlo desde el panel."


def _business(business):
    if business is None:
        from . import services

        business = services.business_info()
    return business


def _owner_block(business):
    get = lambda key: business.get(key) or PENDING  # noqa: E731
    lines = [
        f"Titular: {get('legal_name')}",
        f"NIF/CIF: {get('tax_id')}",
        f"Domicilio: {get('legal_address')}",
        f"Email de contacto: {get('legal_email')}",
    ]
    if business.get("registry_data"):
        lines.append(f"Datos registrales: {business['registry_data']}")
    lines.append(f"Nombre comercial: {business.get('name') or PENDING}")
    return "\n".join(lines)


def _contact(business):
    return business.get("legal_email") or business.get("email") or PENDING


def _program_values():
    from apps.loyalty import conversion, expiry

    rate = conversion.current_rate().points_per_euro
    policy = expiry.active_policy()
    expiry_text = (
        f"Los puntos caducan {policy.months} meses después de ganarse; se avisa por email antes de que caduquen."
        if policy is not None
        else "Hoy los puntos no caducan. Si el titular activa la caducidad, se avisará con antelación y no se aplicará con efecto retroactivo."
    )
    return rate, expiry_text


def legal_notice(business):
    return "\n\n".join([
        DRAFT_NOTICE,
        "1. Datos del titular (art. 10 de la Ley 34/2002, de servicios de la sociedad de la información y de comercio electrónico)",
        _owner_block(business),
        "2. Objeto. Esta web informa sobre la cervecería (carta, eventos y contacto) y da acceso a su programa de puntos y a la reserva de mesas.",
        "3. Condiciones de uso. Quien usa la web se compromete a hacerlo de forma lícita y a no introducir datos falsos o de terceros. Algunas funciones requieren una cuenta y ser mayor de edad.",
        f"4. Venta y consumo de alcohol. La cuenta y el programa de puntos son solo para mayores de {settings.ACCOUNTS_MIN_CUSTOMER_AGE} años. Consume con moderación.",
        "5. Propiedad intelectual. Los textos, imágenes, logotipos y la marca son del titular o se usan con permiso; no se pueden reproducir sin autorización.",
        "6. Responsabilidad. La información de la carta, los precios, la disponibilidad y los eventos puede cambiar; el titular procura mantenerla al día.",
        "7. Protección de datos y cookies: ver la Política de privacidad y la Política de cookies.",
        f"8. Legislación aplicable: la española. Contacto: {_contact(business)}.",
    ])


def privacy(business):
    return "\n\n".join([
        DRAFT_NOTICE,
        "1. Responsable del tratamiento",
        _owner_block(business),
        "2. Qué datos tratamos",
        "Al crear una cuenta: nombre y apellidos, email, contraseña (guardada cifrada, nunca en claro), fecha de nacimiento, código postal, país y localidad, y de forma opcional sexo, teléfono móvil y dirección. Al usar el programa: compras registradas (importe y fecha), puntos, canjes, reservas y tus preferencias de comunicación. No tratamos datos de menores: la cuenta exige ser mayor de edad.",
        "3. Para qué y con qué base legal",
        "a) Gestionar tu cuenta y el programa de puntos (sumar puntos, canjear recompensas, reservas): ejecución de las condiciones del programa que aceptas al registrarte (art. 6.1.b RGPD).\n"
        "b) Enviarte promociones por email o SMS: solo con tu consentimiento, que puedes retirar en cualquier momento desde tu perfil o con el enlace de baja de cada mensaje (art. 6.1.a RGPD y art. 21 LSSI-CE).\n"
        "c) Avisos del servicio (verificación del email, cambios de reserva, caducidad de puntos): ejecución del contrato.\n"
        "d) Seguridad y prevención del fraude (límites de intentos, registro de acciones administrativas): interés legítimo (art. 6.1.f RGPD).\n"
        "e) Estadísticas internas agregadas (por ejemplo, zonas por código postal), sin decisiones automatizadas sobre ti.",
        "4. Quién accede a tus datos",
        "El personal de la cervecería solo ve tu nombre abreviado al registrar compras o validar canjes; la ficha completa solo la ve el titular y cada consulta queda registrada. Proveedores que tratan datos por cuenta del titular (encargados del tratamiento): [pendiente: indicar el alojamiento web, el proveedor de envío de emails, el de SMS si se usa y el de copias de seguridad]. No se ceden datos a terceros salvo obligación legal.",
        "5. Cuánto tiempo los conservamos",
        "Mientras tengas la cuenta. Si la eliminas, se borran o anonimizan tus datos personales y se conservan, sin identificarte, las compras y los movimientos de puntos que el titular debe guardar. [pendiente: plazos concretos de conservación fijados por el asesor].",
        "6. Tus derechos",
        f"Puedes pedir el acceso, la rectificación, la supresión, la oposición, la limitación y la portabilidad de tus datos, y retirar el consentimiento, escribiendo a {_contact(business)}. Muchos datos los puedes cambiar tú mismo en tu perfil. Si crees que no se han atendido tus derechos, puedes reclamar ante la Agencia Española de Protección de Datos (www.aepd.es).",
        "7. Seguridad",
        "Conexión cifrada (HTTPS), contraseñas con hash, acceso por roles, registro de acciones administrativas y copias de seguridad cifradas. Los códigos QR y los enlaces no contienen datos personales.",
        "8. Cookies: ver la Política de cookies.",
    ])


def cookies(business):
    session_days = settings.SESSION_COOKIE_AGE // 86400
    language_days = settings.LANGUAGE_COOKIE_AGE // 86400
    return "\n\n".join([
        DRAFT_NOTICE,
        "Esta web solo usa cookies técnicas y de preferencia, necesarias para que funcione. No usa cookies de analítica, de publicidad ni de terceros, por lo que no necesita tu consentimiento para instalarlas (art. 22.2 LSSI-CE y guía de la AEPD).",
        f"- {settings.SESSION_COOKIE_NAME}: mantiene tu sesión iniciada. Propia. Dura hasta {session_days} días o hasta que cierras sesión.\n"
        f"- {settings.CSRF_COOKIE_NAME}: protege los formularios frente a envíos fraudulentos. Propia. Técnica.\n"
        f"- {settings.LANGUAGE_COOKIE_NAME}: recuerda el idioma que eliges (gallego o castellano). Propia. Dura {language_days} días.",
        "Puedes borrar o bloquear las cookies desde la configuración de tu navegador; si bloqueas las técnicas, no podrás iniciar sesión.",
        f"Si en el futuro se usan otras cookies, se pedirá antes tu consentimiento. Contacto: {_contact(business)}.",
    ])


def program_terms(business):
    rate, expiry_text = _program_values()
    return "\n\n".join([
        DRAFT_NOTICE,
        f"1. Organizador: {business.get('legal_name') or PENDING} ({business.get('name') or PENDING}).",
        f"2. Quién puede participar: personas mayores de {settings.ACCOUNTS_MIN_CUSTOMER_AGE} años con una cuenta y el email verificado. Es gratuito y voluntario.",
        f"3. Cómo se ganan puntos: al pagar en el local, enseñando tu código QR personal. Ahora se dan {rate} puntos por euro, redondeando hacia abajo. Algunas promociones pueden dar puntos extra. Los puntos no tienen valor en dinero y no se pueden vender ni ceder.",
        f"4. Caducidad: {expiry_text}",
        f"5. Recompensas y canjes: se canjean desde la web, que descuenta los puntos y da un código de un solo uso. Hay que recogerla en el local en {settings.REWARDS_CODE_VALIDITY_DAYS} días; si no, el canje caduca y se devuelven los puntos. Las recompensas están sujetas a disponibilidad.",
        "6. Uso indebido: el titular puede anular puntos obtenidos por error o de forma fraudulenta y desactivar cuentas que incumplan estas condiciones.",
        "7. Cambios y fin del programa: el titular puede cambiar estas condiciones o terminar el programa avisando con antelación razonable; los cambios no afectan a los puntos ya ganados de forma retroactiva. [pendiente: plazo de preaviso y qué pasa con los puntos si el programa termina].",
        f"8. Baja: puedes pedir que se elimine tu cuenta cuando quieras escribiendo a {_contact(business)}; los puntos que tengas se pierden.",
        f"9. Contacto: {_contact(business)}. Datos personales: ver la Política de privacidad.",
    ])


_DRAFTS = {
    "aviso-legal": legal_notice,
    "privacidad": privacy,
    "cookies": cookies,
    "condiciones-programa": program_terms,
}


def draft(kind, business=None):
    return _DRAFTS[kind](_business(business))
