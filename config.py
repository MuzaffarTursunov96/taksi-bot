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

# Ilk marta ishga tushganda admins.json bo'sh bo'lsa, shu ro'yxat bilan boshlanadi
# (vergul bilan ajratilgan chat_id'lar). Botni boshqara oladigan shaxslar.
INITIAL_ADMIN_IDS = [
    int(chat_id.strip())
    for chat_id in os.environ.get("OWNER_ID", "").split(",")
    if chat_id.strip()
]

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

# Botni yoqish/o'chirish va AI yoqish/o'chirishga faqat shu YAGONA shaxs ruxsatga ega
# (qolgan asosiy adminlar boshqa hammasini boshqara oladi, lekin buni emas).
ROOT_ADMIN_ID = (
    int(os.environ["ROOT_ADMIN_ID"])
    if os.environ.get("ROOT_ADMIN_ID")
    else (INITIAL_ADMIN_IDS[0] if INITIAL_ADMIN_IDS else None)
)

# Faqat telethon_listener.py uchun kerak (my.telegram.org/apps dan olinadi).
API_ID = int(os.environ["API_ID"]) if os.environ.get("API_ID") else None
API_HASH = os.environ.get("API_HASH", "")

# Yangi akkauntlarni ulashda urinishlarni bir nechta ilova orasida tarqatish uchun
# qo'shimcha api_id/api_hash juftliklari (Telegram'ning shubha aniqlashini kamaytiradi).
# .env'da: API_ID_2, API_HASH_2, API_ID_3, API_HASH_3 ...
API_CREDENTIALS: list[tuple[int, str]] = []
if API_ID and API_HASH:
    API_CREDENTIALS.append((API_ID, API_HASH))
for _i in range(2, 6):
    _aid = os.environ.get(f"API_ID_{_i}")
    _ahash = os.environ.get(f"API_HASH_{_i}")
    if _aid and _ahash:
        API_CREDENTIALS.append((int(_aid), _ahash))

# Fine-tuning tugagach shu yerga fine-tuned model nomi yoziladi
# (masalan: ft:gpt-4o-mini-2024-07-18:...). Bo'sh bo'lsa, standart model ishlatiladi.
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# Botni ushbu shaharlar orasidagi yo'nalishlarga qiziqtiramiz.
# Har bir shahar uchun matnda uchraydigan turli yozilish variantlarini kiriting.
CITY_ALIASES = {
    "Toshkent": ["toshkent", "toskent", "tashkent", "tsh", "тошкент", "ташкент"],
    "Norin": ["norin", "naryn", "норин", "нарын"],
    "Uchqo'rg'on": [
        "uchqo'rg'on", "uchqorgon", "uchqurgan",
        "учқўрғон", "учкургон", "учкурган",
    ],
    "Namangan": ["namangan", "namanga", "наманган"],
    "Xaqqulobod": [
        "xaqqulobod", "haqqulobod", "xaqqulabod", "haqqulabod",
        "хаққулобод", "хаккулобод", "хаккулабод",
    ],
    "Chortoq": ["chortoq", "chortok", "чортоқ", "чорток"],
    "Uychi": ["uychi", "уйчи"],
    "Qo'qon": ["qo'qon", "qoqon", "kokand", "қўқон", "кокон", "коканд"],
    "Qo'g'ay": ["qo'g'ay", "qogay", "kugay", "қўғай", "кугай"],
    "Izboskan": ["izboskan", "избоскан"],
    "Xorazm": ["xorazm", "хоразм"],
    "Buxoro": ["buxoro", "bukhara", "бухоро", "бухара"],
    "Pavorot": ["pavorot", "pavarot", "паворот", "паварот"],
    "Baliqchi": ["baliqchi", "baliqchi", "баликчи", "балиқчи"],
}
