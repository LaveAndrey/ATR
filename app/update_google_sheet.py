import logging
from datetime import datetime
import pytz

def update_google_sheet(auth_google_sheets, SYMBOLS, fetch_weekly_data, calculate_levels, ATR_PERIOD, TIMEZONE, send_telegram_message):
    """Основная функция обновления таблицы"""
    try:
        logging.info("Начало обновления таблицы...")
        sheet = auth_google_sheets()

        # Очистка только данных
        sheet.batch_clear(['A2:G100'])

        # Заголовки
        headers = ['Тикер', 'Открытие недели', 'ATR (14)',
                   'Неделя max', '1/2 неделя max',
                   'Неделя min', '1/2 неделя min']

        if not sheet.row_values(1):
            sheet.append_row(headers)
            sheet.format('A1:G1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })

        # Сбор данных
        rows = []
        for symbol in SYMBOLS:
            try:
                data = fetch_weekly_data(symbol, ATR_PERIOD)
                levels = calculate_levels(data, ATR_PERIOD)
                rows.append([
                    levels['symbol'],
                    float(levels['open']),
                    float(levels['atr']),
                    float(levels['week_max']),
                    float(levels['half_week_max']),
                    float(levels['week_min']),
                    float(levels['half_week_min'])
                ])
                logging.info(f"Данные для {symbol} обработаны")
            except Exception as e:
                logging.error(f"Ошибка обработки {symbol}: {str(e)}")
                continue

        # Запись данных
        if rows:
            sheet.append_rows(rows)
            sheet.format(f'B2:G{len(rows) + 1}', {
                'numberFormat': {'type': 'NUMBER', 'pattern': '#,##0.00'}
            })

        # Метка времени обновления
        update_time = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S')
        sheet.update_cell(len(rows) + 2, 1, f'Последнее обновление: {update_time}')

        logging.info(f"Таблица успешно обновлена в {update_time}")
        return True

    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        send_telegram_message(f"⚠️ Ошибка обновления таблицы: {str(e)}")
        return False
