from dotenv import load_dotenv
import os

load_dotenv()

class Config():
    TELEGRAM_BOT_TOKEN = os.getenv('TOKENTELEGRAM')
    TELEGRAM_CHAT_ID = os.getenv('CHAT_IDTELEGRAM')