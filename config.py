import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Ilk marta ishga tushganda drivers.json bo'sh bo'lsa, shu ro'yxat bilan boshlanadi.
INITIAL_DRIVER_CHAT_IDS = [
    int(chat_id.strip())
    for chat_id in os.environ.get("DRIVER_CHAT_IDS", "").split(",")
    if chat_id.strip()
]

# Shofyorlar ro'yxatini /adddriver, /removedriver orqali boshqara oladigan shaxs.
OWNER_ID = int(os.environ["OWNER_ID"]) if os.environ.get("OWNER_ID") else None

# Ilk marta ishga tushganda groups.json bo'sh bo'lsa, shu ro'yxat bilan boshlanadi
# (vergul bilan ajratilgan chat_id'lar, masalan: -1001234567890,-1009876543210).
INITIAL_MONITORED_GROUP_IDS = [
    int(chat_id.strip())
    for chat_id in os.environ.get("MONITORED_GROUP_IDS", "").split(",")
    if chat_id.strip()
]

# "all" — bot a'zo bo'lgan barcha guruhlarni tinglaydi (default).
# "selected" — faqat yuqoridagi MONITORED_GROUP_IDS (yoki /enablegroup orqali) yoqilganlarni.
DEFAULT_GROUP_MODE = os.environ.get("GROUP_MODE", "all")

# Faqat telethon_listener.py uchun kerak (my.telegram.org/apps dan olinadi).
API_ID = int(os.environ["API_ID"]) if os.environ.get("API_ID") else None
API_HASH = os.environ.get("API_HASH", "")

# Botni ushbu shaharlar orasidagi yo'nalishlarga qiziqtiramiz.
# Har bir shahar uchun matnda uchraydigan turli yozilish variantlarini kiriting.
CITY_ALIASES = {
    "Toshkent": ["toshkent", "toskent", "tashkent", "tsh"],
    "Norin": ["norin", "naryn"],
    "Uchqo'rg'on": ["uchqo'rg'on", "uchqorgon", "uchqurgan", "uchqo'rg'on"],
}
