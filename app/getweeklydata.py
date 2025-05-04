import ccxt
import logging
import pandas as pd

def fetch_weekly_data(symbol, ATR_PERIOD):
    """Получение недельных данных с Binance"""
    exchange = ccxt.mexc({
        'enableRateLimit': True,
        'timeout': 30000
    })

    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1w', limit=ATR_PERIOD + 2)
        if len(ohlcv) < ATR_PERIOD + 1:
            raise ValueError(f"Недостаточно данных для {symbol}")

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['symbol'] = symbol  # Добавляем символ в DataFrame
        return df

    except Exception as e:
        logging.error(f"Ошибка получения данных для {symbol}: {str(e)}")
        raise