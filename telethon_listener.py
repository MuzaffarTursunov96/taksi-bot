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


@client.on(events.NewMessage())
async def on_new_message(event: events.NewMessage.Event) -> None:
    if not (event.is_group or event.is_channel):
        return

    if not storage.is_group_monitored(event.chat_id):
        return

    sender = await event.get_sender()
    if sender is None or getattr(sender, "bot", False):
        return

    chat = await event.get_chat()
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
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            mark = "✅" if storage.is_group_monitored(dialog.id) else "  "
            logger.info("%s %s — %s", mark, dialog.id, dialog.title)

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
