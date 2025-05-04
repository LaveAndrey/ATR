import ccxt
import logging
import time

def check_price_levels(auth_google_sheets, get_levels_from_sheet, SYMBOLS, send_alert, send_telegram_message):
    try:
        sheet = auth_google_sheets()
        levels_data = get_levels_from_sheet(sheet)

        if not levels_data:
            logging.error("Не удалось получить уровни из таблицы")
            return

        exchange = ccxt.mexc({
            'enableRateLimit': True,
            'timeout': 30000
        })

        for symbol in SYMBOLS:
            try:
                if symbol not in levels_data:
                    continue

                levels = levels_data[symbol]
                if not all(isinstance(v, (int, float)) for v in levels.values()):
                    continue

                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']

                # Проверка уровней с учетом лимитов
                if current_price > levels['week_max']:
                    send_alert(symbol, current_price, 'week_max', levels['week_max'])
                elif current_price > levels['half_week_max']:
                    send_alert(symbol, current_price, 'half_week_max', levels['half_week_max'])
                elif current_price < levels['week_min']:
                    send_alert(symbol, current_price, 'week_min', levels['week_min'])
                elif current_price < levels['half_week_min']:
                    send_alert(symbol, current_price, 'half_week_min', levels['half_week_min'])

            except ccxt.NetworkError:
                time.sleep(5)
            except Exception as e:
                logging.error(f"Ошибка проверки {symbol}: {str(e)}")

    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        send_telegram_message(f"⚠️ Ошибка мониторинга: {str(e)}")