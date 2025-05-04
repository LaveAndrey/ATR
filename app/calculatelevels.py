import logging

def calculate_levels(df, ATR_PERIOD):
    """Расчет ATR и ключевых уровней"""
    try:
        historical_data = df.iloc[-(ATR_PERIOD + 1):-1].copy()
        historical_data['prev_close'] = historical_data['close'].shift(1)

        historical_data['tr'] = historical_data.apply(
            lambda x: max(
                x['high'] - x['low'],
                abs(x['high'] - x['prev_close']),
                abs(x['low'] - x['prev_close'])
            ), axis=1
        )

        atr = historical_data['tr'].mean()
        current_week = df.iloc[-1]

        return {
            'symbol': df['symbol'].iloc[0].split('/')[0],  # Получаем символ из DataFrame
            'open': current_week['open'],
            'atr': round(atr, 2),
            'week_max': round(current_week['open'] + atr, 2),
            'half_week_max': round(current_week['open'] + (atr / 2), 2),
            'week_min': round(current_week['open'] - atr, 2),
            'half_week_min': round(current_week['open'] - (atr / 2), 2),
            'timestamp': current_week['timestamp']
        }

    except Exception as e:
        logging.error(f"Ошибка расчета уровней: {str(e)}")
        raise