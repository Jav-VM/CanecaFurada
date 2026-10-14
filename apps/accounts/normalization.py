def normalize_email_address(value):
    """
    Política de emails de la plataforma: se eliminan espacios exteriores y se
    convierte la dirección completa a minúsculas.

    Aunque el RFC permite distinguir mayúsculas en la parte local, en la práctica
    los proveedores no lo hacen y tratar `Ana@x.com` y `ana@x.com` como cuentas
    distintas facilita duplicados y suplantaciones. No se eliminan puntos ni
    sufijos `+etiqueta` porque su significado depende de cada proveedor.
    """
    if value is None:
        return value
    return str(value).strip().lower()
