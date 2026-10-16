import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from telethon import TelegramClient, events

from config import API_HASH, API_ID, BOT_TOKEN
from core import process_text
import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
client = TelegramClient("userbot_session", API_ID, API_HASH)


def _sender_display(sender) -> str:
    if sender is None:
        return "Noma'lum"
    username = getattr(sender, "username", None)
    if username:
        return f"@{username}"
    name = " ".join(
        part
        for part in [getattr(sender, "first_name", None), getattr(sender, "last_name", None)]
        if part
    )
    return name or f"id{getattr(sender, 'id', '?')}"


async def _rescan_dialogs() -> None:
    """Barcha guruh/kanal nomlarini xotiraga yozib qo'yadi (yangi qo'shilganlar ham)."""
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            storage.record_known_group(dialog.id, dialog.title)


async def _periodic_rescan() -> None:
    """10 daqiqada bir marta guruhlar ro'yxatini yangilab turadi — hech narsa qilish
    shart emas, akkaunt yangi guruhga qo'shilsa avtomatik paydo bo'ladi."""
    while True:
        await asyncio.sleep(600)
        try:
            await _rescan_dialogs()
        except Exception:
            logger.exception("Guruhlarni qayta skanerlashda xato")


@client.on(events.ChatAction())
async def on_chat_action(event: events.ChatAction.Event) -> None:
    """Akkaunt yangi guruh/kanalga qo'shilganda darhol ro'yxatga qo'shadi."""
    if not (event.user_joined or event.user_added):
        return
    me = await client.get_me()
    if event.user_id != me.id:
        return
    chat = await event.get_chat()
    title = getattr(chat, "title", None)
    if title:
        storage.record_known_group(event.chat_id, title)
        logger.info("Yangi guruhga qo'shildik: %s — %s", event.chat_id, title)


@client.on(events.NewMessage())
async def on_new_message(event: events.NewMessage.Event) -> None:
    if not (event.is_group or event.is_channel):
        return

    chat = await event.get_chat()
    storage.record_known_group(event.chat_id, getattr(chat, "title", None))

    if not storage.is_group_monitored(event.chat_id):
        return

    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return

    group_kwargs = {
        "group_name": getattr(chat, "title", None),
        "group_username": getattr(chat, "username", None),
        "message_id": event.id,
    }

    if not event.raw_text:
        return

    await process_text(
        bot=bot,
        driver_chat_ids=storage.get_driver_ids(),
        chat_id=event.chat_id,
        user_id=sender.id,
        text=event.raw_text,
        sender_display=_sender_display(sender),
        sender_username=getattr(sender, "username", None),
        **group_kwargs,
    )


async def main() -> None:
    if not API_ID or not API_HASH:
        raise RuntimeError("API_ID va API_HASH .env faylida to'ldirilmagan")

    await client.start()
    logger.info("Telethon userbot ishga tushdi, guruhlar tinglanmoqda...")

    logger.info("A'zo bo'lgan guruh/kanallar ro'yxati (chat_id — nomi):")
    await _rescan_dialogs()
    for chat_id, title in storage.get_known_groups().items():
        mark = "✅" if storage.is_group_monitored(chat_id) else "  "
        logger.info("%s %s — %s", mark, chat_id, title)

    asyncio.create_task(_periodic_rescan())
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
