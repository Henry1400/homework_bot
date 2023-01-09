import logging
import os
import requests
import time
import sys
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import telegram

import exceptions


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет переменные."""
    return all((TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщения в телеграм."""
    logger.info('Начали отправку сообщения')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug("Отправили сообщение через бота")
    except telegram.TelegramError as error:
        message = f'Сообщение не отправилось из-за ошибки: {error}'
        logger.error(message)
        raise exceptions.SendMessageError(message)


def get_api_answer(current_timestamp):
    """Возвращает ответ API."""
    timestamp = current_timestamp or int(time.time())
    arguments = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        logger.info('Получаем ответ API с параметрами: Arguments: {arguments}')
        homework_statuses = requests.get(**arguments)
        # По поводу 'И сам запрос также поместить в try except,
        # на случай ошибки соединения или неверного урла.'
        # Нужно homework_statuses.status_code != HTTPStatus.OK
        # переместить под сам запрос?
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise exceptions.WrongHTTPStatus(
            'Не удалось установить соединение с API-сервисом',
            homework_statuses.status_code,
            homework_statuses.headers,
            homework_statuses.url
        )
    try:
        homework_statuses = homework_statuses.json()
    except Exception as error:
        logger.error(f'Ошибка при обработке json-файла: {error}')
        raise Exception(f'Ошибка при обработке json-файла: {error}')
    return homework_statuses


def check_response(response):
    """Проверяет ответ API."""
    if not isinstance(response, dict):
        logger.error('Ответ вернул не словарь')
        raise TypeError('Ответ вернул не словарь')
    homeworks = response.get('homeworks')
    if homeworks is None:
        logger.error('Ключ homework отсутсвует')
        raise KeyError('Ключ homework отсутсвует')
    if not isinstance(homeworks, list):
        logger.error('Ответ вернулся не в виде списка')
        raise TypeError('Ответ вернулся не в виде списка')
    return homeworks


def parse_status(homework):
    """Проверяет статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError('Ключ homework_name отсутсвует в {homework}')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус {homework_status} неизвестен')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        error_messages = (
            'Переменные отсутствуют'
            'Бот остановлен'
        )
        logger.critical(error_messages)
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_information = {
        'message_name': '',
        'output_text': ''
    }
    information = {
        'message_name': '',
        'output_text': ''
    }
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            homeworks = check_response(response)
            if homeworks:
                status = parse_status(homeworks[0])
                information = status
            else:
                message = 'Статус работы не изменился'
                logger.debug(message)
                information['output_text'] = message
            if information != last_information:
                try:
                    send_message(bot, information['output_text'])
                    last_information = information.copy()
                except exceptions.SendMessageError as error:
                    logger.error(error)
            else:
                logger.debug(
                    'Статус работы не изменился, сообщение не отправлено'
                )
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if information != last_information:
                send_message(bot, information)
                last_information = information.copy()
        finally:
            logger.info('Спящий режим.')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='main.log',
        format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s',
        filemode='w'
    )
    main()
