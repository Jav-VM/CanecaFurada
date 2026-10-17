"""
Ordenación de los listados del dashboard (Fase 18).

Cada listado declara una **lista blanca** de columnas: `{clave: campos}`. La
URL solo elige una clave (`?orden=fecha&dir=desc`); los campos del ORM nunca
salen de la petición. Una clave o dirección desconocida deja el orden por
defecto del selector, sin error.

- `Sort.apply(queryset)`: ordena en la base de datos, con los nulos al final y
  el `id` como desempate (paginación estable).
- `Sort.apply_list(items)`: ordena listas ya calculadas en memoria (empleados,
  zonas); allí cada columna es una función que da el valor de una fila.

Las columnas de estado o tipo se ordenan por su valor interno, no por la
etiqueta traducida.

Una página puede tener dos listados (recompensas y canjes): cada uno usa su
`prefix` para no pisar los parámetros del otro.
"""
from django.db.models import F

ASC = "asc"
DESC = "desc"


class Sort:
    def __init__(self, data, columns, *, prefix=""):
        self.columns = columns
        self.order_param = f"{prefix}orden"
        self.dir_param = f"{prefix}dir"
        key = data.get(self.order_param, "")
        direction = data.get(self.dir_param, "")
        valid = key in columns and direction in (ASC, DESC)
        self.key = key if valid else ""
        self.direction = direction if valid else ""

    def __bool__(self):
        return bool(self.key)

    @property
    def descending(self):
        return self.direction == DESC

    def apply(self, queryset):
        if not self:
            return queryset
        order = []
        for field in (*self.columns[self.key], "id"):
            expression = F(field)
            order.append(expression.desc(nulls_last=True) if self.descending else expression.asc(nulls_last=True))
        return queryset.order_by(*order)

    def apply_list(self, items):
        if not self:
            return list(items)
        value = self.columns[self.key]
        present = [item for item in items if value(item) is not None]
        missing = [item for item in items if value(item) is None]
        return sorted(present, key=value, reverse=self.descending) + missing
