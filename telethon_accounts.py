"""Bir nechta shaxsiy Telegram akkauntini (Telethon orqali) bir vaqtda boshqaradi.

Har bir akkaunt o'zining sessiya fayliga ega, lekin barchasi bitta umumiy
mantiq (xabarlarni tekshirish, guruh nomlarini eslab qolish) orqali ishlaydi.
"""

import asyncio
import logging

from aiogram import Bot
from telethon import TelegramClient, events

from config import API_HASH, API_ID
from core import process_text
import storage

logger = logging.getLogger(__name__)

# owner_user_id -> TelegramClient
_active_clients: dict[int, TelegramClient] = {}


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


def attach_handlers(client: TelegramClient, bot: Bot) -> None:
    """Bitta Telethon mijoziga xabar/guruh hodisalarini ulaydi."""

    @client.on(events.ChatAction())
    async def on_chat_action(event: events.ChatAction.Event) -> None:
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
            group_name=getattr(chat, "title", None),
            group_username=getattr(chat, "username", None),
            message_id=event.id,
        )


async def _notify_group_conflict(bot: Bot, viewer_id: int, chat_id: int, title: str) -> None:
    """Agar shu guruhni allaqachon boshqa birov qo'shgan bo'lsa, ko'rayotgan
    odamga bir martalik xabar beradi (spam qilmaslik uchun)."""
    owner_id = storage.get_group_owner(chat_id)
    if owner_id is None or owner_id == viewer_id:
        return
    if storage.was_conflict_notified(chat_id, viewer_id):
        return
    storage.mark_conflict_notified(chat_id, viewer_id)
    try:
        await bot.send_message(
            viewer_id,
            f"ℹ️ \"{title}\" guruhi allaqachon boshqa birov tomonidan qo'shilgan "
            "va tinglanmoqda — sizga qo'shimcha hech narsa qilish shart emas.",
        )
    except Exception:
        logger.exception("Konflikt xabarini (%s) yuborib bo'lmadi", viewer_id)


async def rescan_dialogs(client: TelegramClient, bot: Bot | None = None, owner_id: int | None = None) -> None:
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            storage.record_known_group(dialog.id, dialog.title)
            if bot is not None and owner_id is not None and storage.is_group_monitored(dialog.id):
                await _notify_group_conflict(bot, owner_id, dialog.id, dialog.title)


async def register_client(owner_id: int, client: TelegramClient, bot: Bot) -> None:
    """Allaqachon ulangan (yoki hozirgina login qilingan) mijozni ishga tushiradi."""
    attach_handlers(client, bot)
    _active_clients[owner_id] = client
    try:
        await rescan_dialogs(client, bot, owner_id)
    except Exception:
        logger.exception("Akkaunt (%s) guruhlarini skanerlashda xato", owner_id)


async def load_all_accounts(bot: Bot) -> None:
    """Saqlangan barcha akkauntlarni ulaydi (server qayta ishga tushganda)."""
    for owner_id, info in storage.get_linked_accounts().items():
        try:
            client = TelegramClient(info["session"], API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("Akkaunt (%s) sessiyasi yaroqsiz, o'tkazib yuboriladi", owner_id)
                continue
            await register_client(owner_id, client, bot)
            logger.info("Akkaunt ulandi: owner=%s", owner_id)
        except Exception:
            logger.exception("Akkaunt (%s) ulanmadi", owner_id)


async def periodic_rescan(bot: Bot) -> None:
    """10 daqiqada bir marta barcha ulangan akkauntlarning guruhlarini yangilaydi."""
    while True:
        await asyncio.sleep(600)
        for owner_id, client in list(_active_clients.items()):
            try:
                await rescan_dialogs(client, bot, owner_id)
            except Exception:
                logger.exception("Akkaunt (%s) qayta skanerlashda xato", owner_id)


def get_active_owner_ids() -> list[int]:
    return list(_active_clients.keys())
