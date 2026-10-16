"""Bir martalik skript: tinglanayotgan guruhlarning ESKI xabarlarini o'qib,
OpenAI orqali tasniflab, training_data.jsonl fayliga yozadi.

Ishga tushirish: venv/bin/python backfill_training_data.py
"""

import asyncio
import logging
import shutil
from pathlib import Path

from telethon import TelegramClient

from config import API_HASH, API_ID
import storage
from filters import OpenAIQuotaExceeded, classify_route, quick_prefilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Har bir OpenAI so'rovi orasidagi kutish (limitga tegib qolmaslik uchun).
DELAY_BETWEEN_CALLS = 1.3

# Har bir guruhdan nechta oxirgi xabarni tekshirish (None = hammasi).
# Sinov uchun kichik son (200) — keyin katta hajmda ishga tushirish uchun oshiring.
MESSAGES_PER_GROUP = 200

# Asosiy tinglash jarayoni (taksibot-telethon.service) bilan session faylini
# baham ko'rmaslik uchun uning nusxasidan foydalanamiz.
_SRC_SESSION = Path("userbot_session.session")
_BACKFILL_SESSION = "userbot_session_backfill"


async def main() -> None:
    dst = Path(f"{_BACKFILL_SESSION}.session")
    if _SRC_SESSION.exists() and not dst.exists():
        shutil.copy(_SRC_SESSION, dst)
        logger.info("Session nusxalandi: %s", dst)

    client = TelegramClient(_BACKFILL_SESSION, API_ID, API_HASH)
    await client.start()

    groups = storage.get_monitored_groups()
    if not groups:
        logger.warning("Tinglanayotgan guruh yo'q — avval botda guruh yoqing.")
        await client.disconnect()
        return

    total_checked = 0
    total_saved = 0

    for chat_id, title in groups.items():
        logger.info("--- %s (%s) ---", title, chat_id)
        group_checked = 0
        group_saved = 0
        try:
            async for message in client.iter_messages(chat_id, limit=MESSAGES_PER_GROUP):
                if not message.text or not quick_prefilter(message.text):
                    continue
                try:
                    result = await classify_route(message.text)
                except OpenAIQuotaExceeded:
                    logger.error("OpenAI balansi tugadi — skript to'xtatildi.")
                    await client.disconnect()
                    logger.info(
                        "Jami tekshirildi: %s, saqlandi: %s", total_checked, total_saved
                    )
                    return

                group_checked += 1
                total_checked += 1
                if result:
                    group_saved += 1
                    total_saved += 1
                await asyncio.sleep(DELAY_BETWEEN_CALLS)
        except Exception:
            logger.exception("'%s' guruhini o'qishda xato, keyingisiga o'tamiz", title)
            continue

        logger.info("%s: %s ta tekshirildi, %s ta saqlandi", title, group_checked, group_saved)

    await client.disconnect()
    logger.info("TUGADI. Jami tekshirildi: %s, saqlandi: %s", total_checked, total_saved)


if __name__ == "__main__":
    asyncio.run(main())
