import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

import storage

logger = logging.getLogger(__name__)

PUBLIC_COMMANDS = [
    BotCommand(command="menu", description="Buyruqlar ro'yxati"),
    BotCommand(command="mening_id", description="Chat ID'ingizni bilish"),
]

ADMIN_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand(command="holat", description="Bot holatini ko'rish"),
    BotCommand(command="botni_yoqish", description="Botni yoqish"),
    BotCommand(command="botni_ochirish", description="Botni o'chirish"),
    BotCommand(command="chatgpt_yoqish", description="AI tahlilini yoqish"),
    BotCommand(command="chatgpt_ochirish", description="AI tahlilini o'chirish"),
    BotCommand(command="guruhlar", description="Tinglanayotgan guruhlar ro'yxati"),
    BotCommand(command="guruh_yoqish", description="Guruhni yoqish"),
    BotCommand(command="guruh_ochirish", description="Guruhni o'chirish"),
    BotCommand(command="hamma_guruh", description="Barcha guruhlarni tinglash"),
    BotCommand(command="tanlangan_guruhlar", description="Tanlangan guruhlarni tinglash"),
    BotCommand(command="shofyorlar", description="Shofyorlar ro'yxati"),
    BotCommand(command="shofyor_qoshish", description="Shofyor qo'shish"),
    BotCommand(command="shofyor_ochirish", description="Shofyorni o'chirish"),
]

FOUNDER_COMMANDS = ADMIN_COMMANDS + [
    BotCommand(command="adminlar", description="Adminlar ro'yxati"),
    BotCommand(command="admin_qoshish", description="Yangi admin qo'shish"),
    BotCommand(command="admin_ochirish", description="Adminlikdan chiqarish"),
]


async def sync_admin_commands(bot: Bot, chat_id: int) -> None:
    """Bitta adminning shaxsiy chatida ko'rinadigan buyruqlar menyusini yangilaydi."""
    commands = FOUNDER_COMMANDS if storage.is_founder(chat_id) else ADMIN_COMMANDS
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=chat_id))
    except Exception:
        # Foydalanuvchi botga hali /start yozmagan bo'lishi mumkin — muammo emas,
        # birinchi /start yozganda umumiy (default) menyu ko'rinadi.
        logger.warning("Admin (%s) uchun buyruqlar menyusini sozlab bo'lmadi", chat_id)


async def sync_all_commands(bot: Bot) -> None:
    """Bot ishga tushganda barcha adminlar uchun menyularni yangilaydi."""
    await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in storage.get_admin_ids():
        await sync_admin_commands(bot, admin_id)
