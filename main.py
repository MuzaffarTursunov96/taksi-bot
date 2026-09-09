"""Yagona kirish nuqtasi: aiogram bot (buyruqlar/menyu) va bir nechta Telethon
akkauntlarini (guruhlarni tinglash) bitta dasturda birga ishga tushiradi."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from admin_handlers import router as admin_router
import commands
from config import BOT_TOKEN
from handlers import router as handlers_router
from link_account import router as link_router
from menu_handlers import router as menu_router
import telethon_accounts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(link_router)
    dp.include_router(menu_router)
    dp.include_router(handlers_router)

    await commands.sync_all_commands(bot)

    logger.info("Saqlangan Telethon akkauntlari ulanmoqda...")
    await telethon_accounts.load_all_accounts(bot)
    asyncio.create_task(telethon_accounts.periodic_rescan(bot))

    logger.info("Bot ishga tushdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
