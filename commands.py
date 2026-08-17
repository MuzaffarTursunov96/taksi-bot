import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

import storage

logger = logging.getLogger(__name__)

# Endi hammasi tugmali menyu (reply/inline keyboard) orqali boshqariladi,
# shuning uchun "/" buyruqlar ro'yxatida faqat /start qoladi.
PUBLIC_COMMANDS = [
    BotCommand(command="start", description="Menyuni ochish"),
]

ADMIN_COMMANDS = PUBLIC_COMMANDS
FOUNDER_COMMANDS = PUBLIC_COMMANDS


async def sync_admin_commands(bot: Bot, chat_id: int) -> None:
    """Bitta adminning shaxsiy chatida ko'rinadigan buyruqlar menyusini yangilaydi."""
    try:
        await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeChat(chat_id=chat_id))
    except Exception:
        # Foydalanuvchi botga hali /start yozmagan bo'lishi mumkin — muammo emas,
        # birinchi /start yozganda umumiy (default) menyu ko'rinadi.
        logger.warning("Admin (%s) uchun buyruqlar menyusini sozlab bo'lmadi", chat_id)


async def sync_all_commands(bot: Bot) -> None:
    """Bot ishga tushganda barcha adminlar uchun menyularni yangilaydi."""
    await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in storage.get_admin_ids():
        await sync_admin_commands(bot, admin_id)
