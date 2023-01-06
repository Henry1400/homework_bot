class IncorrectRequestStatus(Exception):
    """Вызывается при получении некорректного статуса запроса к API."""

    pass


class APIRequestError(Exception):
    """Вызывается при ошибке запроса к API."""

    pass