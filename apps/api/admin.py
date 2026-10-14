"""
La app de lista negra de simplejwt registra en el admin sus tokens, y la ficha
de un `OutstandingToken` muestra el refresh token completo. El propietario
(superusuario) podría copiarlo y actuar como cualquier cliente, así que esos
modelos no se exponen en el admin. Para cerrar sesiones se usan
`POST /api/v1/auth/logout-all/` o la desactivación de la cuenta.
"""
from django.contrib import admin
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

for model in (OutstandingToken, BlacklistedToken):
    if admin.site.is_registered(model):
        admin.site.unregister(model)
