import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import pytz
import logging
import time
from datetime import timedelta

from app.check_price_levels import check_price_levels
from app.telegrammes import send_telegram_message
from app.getweeklydata import fetch_weekly_data
from app.calculatelevels import calculate_levels
from app.update_google_sheet import update_google_sheet
from app.config import Config

# Настройки
SPREADSHEET_ID = Config.SHEETS_ID
CHECK_INTERVAL = 5  # минут
CREDS_FILE = 'credentials.json'
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'BNB/USDT', 'SOL/USDT', 'DOGE/USDT',
           'ADA/USDT', 'TRX/USDT', 'SUI/USDT', 'AVAX/USDT', 'NEAR/USDT', 'TRUMP/USDT', 'XLM/USDT']
ATR_PERIOD = 14
TIME_TO_RUN = '3:01'  # Время запуска (каждый понедельник)
TIMEZONE = 'Europe/Moscow'  # Часовой пояс

DELAY_BETWEEN_MESSAGES = 3

signal_counters = {}  # Формат: {'BTC/USDT': {'week_max': timestamp, ...}}
last_reset_time = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/atr_updater.log'),
        logging.StreamHandler()
    ]
)


def reset_counters_if_needed():
    """Сбрасывает счетчики только в понедельник в 3:00"""
    global last_reset_time, signal_counters
    now = datetime.now(pytz.timezone(TIMEZONE))

    # Проверяем, что:
    # 1. Сегодня понедельник (weekday=0)
    # 2. Время >= 3:00
    # 3. С момента последнего сброса прошла неделя (или он еще не выполнялся)
    if (
        now.weekday() == 0  # Понедельник
        and now.hour >= 3   # После 3:00
        and (
            last_reset_time is None
            or (now - last_reset_time) >= timedelta(days=7)
        )
    ):
        signal_counters = {}
        last_reset_time = now.replace(hour=3, minute=0, second=0, microsecond=0)
        logging.info("Счетчики сигналов сброшены (еженедельно в понедельник в 3:00)")
        send_telegram_message("🔄 Счетчики сигналов сброшены - начата новая неделя")


def can_send_alert(symbol, level_type):
    """Проверяет можно ли отправить сигнал"""
    reset_counters_if_needed()

    if symbol not in signal_counters:
        signal_counters[symbol] = {}

    # Максимум 4 уникальных типа сигналов на монету
    if len(signal_counters[symbol]) >= 4:
        return False

    # Если сигнал такого типа уже был
    if level_type in signal_counters[symbol]:
        return False

    return True


def mark_alert_sent(symbol, level_type):
    """Помечает сигнал как отправленный"""
    signal_counters[symbol][level_type] = datetime.now(pytz.timezone(TIMEZONE))
    logging.info(f"Зарегистрирован сигнал {level_type} для {symbol}. Всего: {len(signal_counters[symbol])}/4")


def parse_number(value):
    """
    Преобразует строку с числами в float и ДЕЛИТ НА 100
    Обрабатывает случаи: '1,79', '179', '50.0', '103 328.89'
    """
    try:
        if isinstance(value, (int, float)):
            return float(value) / 100  # Делим даже если число уже в правильном формате

        # Очистка строки
        cleaned = str(value).strip()
        cleaned = cleaned.replace('\xa0', '').replace(' ', '').replace(',', '.')

        # Удаление лишних символов
        cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')

        if not cleaned:
            return 0.0

        # Преобразуем в float и ДЕЛИМ НА 100
        return round(float(cleaned), 2)

    except Exception as e:
        logging.error(f"Ошибка преобразования '{value}': {str(e)}")
        return 0.0
def auth_google_sheets():
    """Аутентификация в Google Sheets"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1


def get_levels_from_sheet(sheet):
    levels_data = {}
    try:
        records = sheet.get_all_records()
        for record in records:
            try:
                symbol = record.get('Тикер', '').strip()
                if not symbol:
                    continue

                symbol += '/USDT'

                # Добавляем проверку каждого значения
                levels_data[symbol] = {
                    'week_max': parse_number(record.get('Неделя max', 0)),
                    'half_week_max': parse_number(record.get('1/2 неделя max', 0)),
                    'week_min': parse_number(record.get('Неделя min', 0)),
                    'half_week_min': parse_number(record.get('1/2 неделя min', 0))
                }

                logging.debug(f"Уровни для {symbol}: {levels_data[symbol]}")

            except Exception as e:
                logging.error(f"Ошибка обработки строки: {e}\nДанные: {record}")
                continue

    except Exception as e:
        logging.error(f"Ошибка чтения таблицы: {e}")

    return levels_data



def send_alert(symbol, price, level_type, level_value):
    if not can_send_alert(symbol, level_type):
        logging.warning(f"Лимит сигналов для {symbol} достиг (4/неделю) или сигнал {level_type} уже был")
        return False

    level_names = {
        'week_max': 'Недельный максимум',
        'half_week_max': 'Половина недельного максимума',
        'week_min': 'Недельный минимум',
        'half_week_min': 'Половина недельного минимума'
    }

    message = (
        f"🚨 <b>{symbol}</b>\n"
        f"📊 Текущая цена: <code>{float(price):.2f}</code>\n"
        f"🎯 {level_names[level_type]}: <code>{float(level_value):.2f}</code>\n"
        f"⏰ Время: {datetime.now(pytz.timezone(TIMEZONE)).strftime('%H:%M:%S')}\n"
    )

    try:
        if send_telegram_message(message):
            mark_alert_sent(symbol, level_type)
            return True
        return False
    except Exception as e:
        logging.error(f"Ошибка отправки: {str(e)}")
        return False


def send_report_for_symbol(symbol):
    """Отправка отчета для одного символа"""
    try:
        data = fetch_weekly_data(symbol, ATR_PERIOD)
        levels = calculate_levels(data, ATR_PERIOD)

        message = (
            f"<b>🔹 {levels['symbol']}</b>\n"
            f"📅 Дата: {levels['timestamp'].strftime('%Y-%m-%d')}\n\n"
            f"▫️ Неделя max: <code>{levels['week_max']:.2f}</code>\n"
            f"▫️ 1/2 max: <code>{levels['half_week_max']:.2f}</code>\n"
            f"▫️ Неделя min: <code>{levels['week_min']:.2f}</code>\n"
            f"▫️ 1/2 min: <code>{levels['half_week_min']:.2f}</code>"
        )

        if send_telegram_message(message):
            logging.info(f"Отчет для {levels['symbol']} успешно отправлен")
            return True
        return False

    except Exception as e:
        logging.error(f"Ошибка обработки {symbol}: {str(e)}")
        return False


def generate_report():
    """Генерация и отправка отчетов с задержкой"""
    try:
        logging.info("Начало отправки отчетов...")

        # Отправляем заголовочное сообщение
        header_message = (
            f"<b>📊 Еженедельный ATR отчет</b>\n"
            f"⏰ Время: {datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M')}\n"
            f"⏳ Задержка между сообщениями: {DELAY_BETWEEN_MESSAGES} сек."
        )
        send_telegram_message(header_message)

        # Отправляем отчеты по каждому символу с задержкой
        for symbol in SYMBOLS:
            success = send_report_for_symbol(symbol)
            if not success:
                logging.error(f"Не удалось отправить отчет для {symbol}")
            if SYMBOLS.index(symbol) < len(SYMBOLS) - 1:
                time.sleep(DELAY_BETWEEN_MESSAGES)

        logging.info("Все отчеты отправлены")

    except Exception as e:
        logging.error(f"Ошибка генерации отчета: {str(e)}")
        send_telegram_message(f"⚠️ Ошибка генерации отчета: {str(e)}")


def main():
    """Запускает планировщик"""
    try:
        scheduler = BlockingScheduler(timezone=pytz.timezone(TIMEZONE))
        hour, minute = map(int, TIME_TO_RUN.split(':'))

        scheduler.add_job(
            reset_counters_if_needed,
            'cron',
            day_of_week='mon',
            hour=3,
            minute=0,
            name="Reset signal counters"
        )

        # Ежедневная проверка цен
        scheduler.add_job(
            lambda: check_price_levels(auth_google_sheets, get_levels_from_sheet, SYMBOLS, send_alert,
                                       send_telegram_message),
            'interval',
            minutes=CHECK_INTERVAL,
            misfire_grace_time=300
        )

        # Еженедельный отчет (в понедельник)
        scheduler.add_job(
            generate_report,
            'cron',
            day_of_week='mon',
            hour=hour,
            minute=minute,
            misfire_grace_time=3600
        )

        # Еженедельное обновление таблицы (в понедельник)
        scheduler.add_job(
            lambda: update_google_sheet(auth_google_sheets, SYMBOLS, fetch_weekly_data, calculate_levels, ATR_PERIOD, TIMEZONE, send_telegram_message),
            'cron',
            day_of_week='mon',
            hour=hour,
            minute=minute,
            misfire_grace_time=3600
        )

        # Уведомление о запуске
        send_telegram_message(
            f"🔔 Система мониторинга запущена\n"
            f"⏳ Проверка цен каждые {CHECK_INTERVAL} минут\n"
            f"📅 Еженедельный отчет в {TIME_TO_RUN} по МСК"
        )

        logging.info(f"Планировщик запущен. Проверка цен каждые {CHECK_INTERVAL} минут")
        scheduler.start()

    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        send_telegram_message(f"❌ Критическая ошибка системы: {str(e)}")


if __name__ == "__main__":
    main()