"""
Serializadores de la API v1.

Todos son `Serializer` con campos explícitos (nunca `ModelSerializer` con
`__all__`): la entrada solo acepta los campos declarados y la salida solo
devuelve los necesarios para cada operación. Los campos que el cliente no
puede modificar (rol, saldo, puntos, estado, auditoría, identificadores) no
existen en los serializadores de entrada; los que se ignoren no producen
error, pero nunca llegan a los servicios.
"""
