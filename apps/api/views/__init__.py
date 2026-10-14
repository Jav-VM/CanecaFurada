"""
Vistas de la API v1. Solo presentación: validan la entrada con serializadores
explícitos, comprueban permisos y llaman a los mismos servicios y selectores
que la web. Siempre actúan sobre `request.user`; los objetos se buscan por
`public_id` dentro de lo que el usuario puede ver, y lo ajeno responde 404.
"""
