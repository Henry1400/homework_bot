import logging
import os
import requests
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import telegram


load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s',
    filemode='w'
)
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
    if (TELEGRAM_TOKEN is None or PRACTICUM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщения в телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug("Отправили сообщение через бота")
    except Exception:
        logger.error('Сообщение не отправилось')


def get_api_answer(current_timestamp):
    """Возвращает ответ API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params
                                         )
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error('Не удалось установить соединение с API-сервисом ')
        raise Exception('Не удалось установить соединение с API-сервисом ')
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
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутсвует')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус {homework_status} неизвестен')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        error_messages = (
            'Переменные отсутствуют'
            'Бот остановле.'
        )
        logger.critical(error_messages)
        return None
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
                information['message_name'] = status
                information['output_text'] = status
            else:
                message = 'Статус работы не изменился'
                logger.debug(message)
                information['output_text'] = message
            if information != last_information:
                send_message(bot, information['output_text'])
                last_information = information.copy()
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
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
