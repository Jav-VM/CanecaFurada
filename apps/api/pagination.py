from rest_framework import pagination


class PageNumberPagination(pagination.PageNumberPagination):
    """
    `?page=N` (desde 1) y `?page_size=M` (máximo 50). Respuesta:
    `{"count", "next", "previous", "results"}`. Una página fuera de rango da 404.
    El límite impide descargas masivas en una sola petición.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
