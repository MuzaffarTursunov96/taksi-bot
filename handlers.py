from aiogram import F, Router
from aiogram.types import Message

from core import process_text
import storage

router = Router()


def _sender_link(message: Message) -> str:
    user = message.from_user
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{user.full_name}</a>'


def _group_kwargs(message: Message) -> dict:
    return {
        "group_name": message.chat.title,
        "group_username": message.chat.username,
        "message_id": message.message_id,
    }


@router.message(F.contact)
async def on_contact_shared(message: Message) -> None:
    """Odam guruhda o'z kontaktini ulashsa (masalan javob sifatida)."""
    if not storage.is_group_monitored(message.chat.id):
        return
    reply = message.reply_to_message
    if not reply or not reply.text:
        return
    await process_text(
        bot=message.bot,
        driver_chat_ids=storage.get_driver_ids(),
        chat_id=message.chat.id,
        user_id=reply.from_user.id,
        text=reply.text,
        sender_display=_sender_link(reply),
        sender_username=reply.from_user.username,
        contact_phone=message.contact.phone_number,
        **_group_kwargs(reply),
    )


@router.message(F.text)
async def on_group_text(message: Message) -> None:
    if not storage.is_group_monitored(message.chat.id):
        return
    await process_text(
        bot=message.bot,
        driver_chat_ids=storage.get_driver_ids(),
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        text=message.text,
        sender_display=_sender_link(message),
        sender_username=message.from_user.username,
        **_group_kwargs(message),
    )
