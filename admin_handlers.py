from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID
import storage

router = Router()


@router.message(Command("myid", "mening_id"))
async def cmd_myid(message: Message) -> None:
    await message.reply(f"Sizning chat ID'ingiz: <code>{message.chat.id}</code>")


@router.message(Command("adddriver", "shofyor_qoshish"), F.from_user.id == OWNER_ID)
async def cmd_add_driver(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.reply("Foydalanish: <code>/shofyor_qoshish 123456789</code>")
        return

    chat_id = int(parts[1].strip())
    if storage.add_driver_id(chat_id):
        await message.reply(f"✅ {chat_id} shofyorlar ro'yxatiga qo'shildi.")
    else:
        await message.reply("Bu chat ID allaqachon ro'yxatda bor.")


@router.message(Command("removedriver", "shofyor_ochirish"), F.from_user.id == OWNER_ID)
async def cmd_remove_driver(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.reply("Foydalanish: <code>/shofyor_ochirish 123456789</code>")
        return

    chat_id = int(parts[1].strip())
    if storage.remove_driver_id(chat_id):
        await message.reply(f"✅ {chat_id} ro'yxatdan o'chirildi.")
    else:
        await message.reply("Bu chat ID ro'yxatda topilmadi.")


@router.message(Command("listdrivers", "shofyorlar"), F.from_user.id == OWNER_ID)
async def cmd_list_drivers(message: Message) -> None:
    driver_ids = storage.get_driver_ids()
    if not driver_ids:
        await message.reply("Ro'yxat bo'sh.")
        return
    text = "\n".join(f"• <code>{chat_id}</code>" for chat_id in driver_ids)
    await message.reply(f"Shofyorlar ro'yxati:\n{text}")


@router.message(Command("enablegroup", "guruh_yoqish"), F.from_user.id == OWNER_ID)
async def cmd_enable_group(message: Message) -> None:
    """Shu guruhda yozilsa — o'sha guruhni yoqadi. DM'da chat_id bilan ham ishlaydi."""
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip().lstrip("-").isdigit():
        chat_id = int(parts[1].strip())
        title = f"chat {chat_id}"
    elif message.chat.type != "private":
        chat_id = message.chat.id
        title = message.chat.title or str(chat_id)
    else:
        await message.reply(
            "Buni guruhning ichida yozing, yoki: <code>/guruh_yoqish -100123456789</code>"
        )
        return

    storage.enable_group(chat_id, title)
    await message.reply(f"✅ \"{title}\" ({chat_id}) endi tinglanadi.")


@router.message(Command("disablegroup", "guruh_ochirish"), F.from_user.id == OWNER_ID)
async def cmd_disable_group(message: Message) -> None:
    """Shu guruhda yozilsa — o'sha guruhni o'chiradi. DM'da chat_id bilan ham ishlaydi."""
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip().lstrip("-").isdigit():
        chat_id = int(parts[1].strip())
    elif message.chat.type != "private":
        chat_id = message.chat.id
    else:
        await message.reply(
            "Buni guruhning ichida yozing, yoki: <code>/guruh_ochirish -100123456789</code>"
        )
        return

    if storage.disable_group(chat_id):
        await message.reply(f"✅ {chat_id} endi tinglanmaydi.")
    else:
        await message.reply("Bu guruh ro'yxatda topilmadi.")


@router.message(Command("listgroups", "guruhlar"), F.from_user.id == OWNER_ID)
async def cmd_list_groups(message: Message) -> None:
    mode = storage.get_group_mode()
    if mode == "all":
        await message.reply(
            "🌐 Rejim: <b>HAMMASI</b> — bot a'zo bo'lgan barcha guruhlarni tinglaydi.\n"
            "Faqat tanlangan guruhlarga cheklash uchun: <code>/tanlangan_guruhlar</code>"
        )
        return

    groups = storage.get_monitored_groups()
    if not groups:
        await message.reply(
            "🎯 Rejim: <b>TANLANGAN</b>, lekin ro'yxat bo'sh — hech qanday guruh tinglanmayapti.\n"
            "Guruhni yoqish uchun o'sha guruhda <code>/guruh_yoqish</code> deb yozing."
        )
        return
    text = "\n".join(f"• {title} — <code>{chat_id}</code>" for chat_id, title in groups.items())
    await message.reply(f"🎯 Rejim: <b>TANLANGAN</b>\nTinglanayotgan guruhlar:\n{text}")


@router.message(Command("listenall", "hamma_guruh"), F.from_user.id == OWNER_ID)
async def cmd_listen_all(message: Message) -> None:
    storage.set_group_mode("all")
    await message.reply("✅ Endi bot a'zo bo'lgan <b>barcha</b> guruhlarni tinglaydi.")


@router.message(Command("listenselected", "tanlangan_guruhlar"), F.from_user.id == OWNER_ID)
async def cmd_listen_selected(message: Message) -> None:
    storage.set_group_mode("selected")
    await message.reply(
        "✅ Endi bot faqat <code>/guruh_yoqish</code> orqali yoqilgan guruhlarni tinglaydi.\n"
        "Joriy ro'yxatni <code>/guruhlar</code> bilan ko'rishingiz mumkin."
    )


@router.message(Command("pausebot", "botni_ochirish"), F.from_user.id == OWNER_ID)
async def cmd_pause_bot(message: Message) -> None:
    storage.set_processing_enabled(False)
    await message.reply(
        "⏸ Bot o'chirildi — xabarlar endi tekshirilmaydi, OpenAI'ga so'rov yuborilmaydi.\n"
        "Qayta yoqish uchun: <code>/botni_yoqish</code>"
    )


@router.message(Command("resumebot", "botni_yoqish"), F.from_user.id == OWNER_ID)
async def cmd_resume_bot(message: Message) -> None:
    storage.set_processing_enabled(True)
    await message.reply("▶️ Bot yoqildi — xabarlar tekshirilmoqda.")


@router.message(Command("status", "holat"), F.from_user.id == OWNER_ID)
async def cmd_status(message: Message) -> None:
    enabled = storage.is_processing_enabled()
    state = "▶️ YOQILGAN" if enabled else "⏸ O'CHIRILGAN"
    await message.reply(f"Bot holati: <b>{state}</b>")
