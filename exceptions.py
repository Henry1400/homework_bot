class SendMessageError(Exception):
    """Ошибка при отправке сообщения"""
    pass


class WrongHTTPStatus(Exception):
    '''Ошибка соединения'''
    pass
