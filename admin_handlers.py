from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommandScopeChat, Message

import commands
import storage

router = Router()


def _is_admin(message: Message) -> bool:
    return storage.is_admin(message.from_user.id)


def _is_founder(message: Message) -> bool:
    return storage.is_founder(message.from_user.id)


@router.message(Command("myid", "mening_id"))
async def cmd_myid(message: Message) -> None:
    await message.reply(f"Sizning chat ID'ingiz: <code>{message.chat.id}</code>")


@router.message(Command("adminadd", "admin_qoshish"), _is_founder)
async def cmd_add_admin(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.reply("Foydalanish: <code>/admin_qoshish 123456789</code>")
        return

    chat_id = int(parts[1].strip())
    if storage.add_admin_id(chat_id):
        await commands.sync_admin_commands(message.bot, chat_id)
        await message.reply(f"✅ {chat_id} adminlar ro'yxatiga qo'shildi.")
    else:
        await message.reply("Bu chat ID allaqachon admin.")


@router.message(Command("adminremove", "admin_ochirish"), _is_founder)
async def cmd_remove_admin(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().lstrip("-").isdigit():
        await message.reply("Foydalanish: <code>/admin_ochirish 123456789</code>")
        return

    chat_id = int(parts[1].strip())
    if storage.remove_admin_id(chat_id):
        try:
            await message.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
        except Exception:
            pass
        await message.reply(f"✅ {chat_id} adminlikdan chiqarildi.")
    else:
        await message.reply(
            "Bu chat ID admin emas, yoki bu asosiy admin — asosiy adminlarni "
            "hech kim (bir-birini ham) o'chira olmaydi."
        )


@router.message(Command("adminlist", "adminlar"), _is_admin)
async def cmd_list_admins(message: Message) -> None:
    admin_ids = storage.get_admin_ids()
    text = "\n".join(f"• <code>{chat_id}</code>" for chat_id in admin_ids)
    await message.reply(f"Adminlar ro'yxati:\n{text}")


@router.message(Command("adddriver", "shofyor_qoshish"), _is_admin)
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


@router.message(Command("removedriver", "shofyor_ochirish"), _is_admin)
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


@router.message(Command("listdrivers", "shofyorlar"), _is_admin)
async def cmd_list_drivers(message: Message) -> None:
    driver_ids = storage.get_driver_ids()
    if not driver_ids:
        await message.reply("Ro'yxat bo'sh.")
        return
    text = "\n".join(f"• <code>{chat_id}</code>" for chat_id in driver_ids)
    await message.reply(f"Shofyorlar ro'yxati:\n{text}")


@router.message(Command("enablegroup", "guruh_yoqish"), _is_admin)
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


@router.message(Command("disablegroup", "guruh_ochirish"), _is_admin)
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


@router.message(Command("listgroups", "guruhlar"), _is_admin)
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


@router.message(Command("listenall", "hamma_guruh"), _is_admin)
async def cmd_listen_all(message: Message) -> None:
    storage.set_group_mode("all")
    await message.reply("✅ Endi bot a'zo bo'lgan <b>barcha</b> guruhlarni tinglaydi.")


@router.message(Command("listenselected", "tanlangan_guruhlar"), _is_admin)
async def cmd_listen_selected(message: Message) -> None:
    storage.set_group_mode("selected")
    await message.reply(
        "✅ Endi bot faqat <code>/guruh_yoqish</code> orqali yoqilgan guruhlarni tinglaydi.\n"
        "Joriy ro'yxatni <code>/guruhlar</code> bilan ko'rishingiz mumkin."
    )


@router.message(Command("pausebot", "botni_ochirish"), _is_admin)
async def cmd_pause_bot(message: Message) -> None:
    storage.set_processing_enabled(False)
    await message.reply(
        "⏸ Bot o'chirildi — xabarlar endi tekshirilmaydi, OpenAI'ga so'rov yuborilmaydi.\n"
        "Qayta yoqish uchun: <code>/botni_yoqish</code>"
    )


@router.message(Command("resumebot", "botni_yoqish"), _is_admin)
async def cmd_resume_bot(message: Message) -> None:
    storage.set_processing_enabled(True)
    await message.reply("▶️ Bot yoqildi — xabarlar tekshirilmoqda.")


@router.message(Command("aion", "chatgpt_yoqish"), _is_admin)
async def cmd_ai_on(message: Message) -> None:
    storage.set_ai_enabled(True)
    await message.reply(
        "✅ ChatGPT (OpenAI) tahlili yoqildi — xabarlar aniq tasniflanadi "
        "(yo'lovchi/shofyor, yo'nalish)."
    )


@router.message(Command("aioff", "chatgpt_ochirish"), _is_admin)
async def cmd_ai_off(message: Message) -> None:
    storage.set_ai_enabled(False)
    await message.reply(
        "⏸ ChatGPT (OpenAI) tahlili o'chirildi — endi shahar nomi topilgan har qanday "
        "xabar tekshirilmasdan (kamroq aniq, lekin bepul) forward qilinadi.\n"
        "Qayta yoqish uchun: <code>/chatgpt_yoqish</code>"
    )


@router.message(Command("status", "holat"), _is_admin)
async def cmd_status(message: Message) -> None:
    bot_enabled = storage.is_processing_enabled()
    ai_enabled = storage.is_ai_enabled()
    mode = storage.get_group_mode()
    bot_state = "▶️ YOQILGAN" if bot_enabled else "⏸ O'CHIRILGAN"
    ai_state = "▶️ YOQILGAN" if ai_enabled else "⏸ O'CHIRILGAN"
    mode_state = "🌐 HAMMASI" if mode == "all" else "🎯 TANLANGAN"
    await message.reply(
        f"🤖 Bot: <b>{bot_state}</b>\n"
        f"🧠 ChatGPT tahlili: <b>{ai_state}</b>\n"
        f"👥 Guruh rejimi: <b>{mode_state}</b>"
    )


@router.message(Command("menu", "yordam", "help"))
async def cmd_menu(message: Message) -> None:
    if not storage.is_admin(message.from_user.id):
        await message.reply(
            "🤖 Bu bot yo'nalish e'lonlarini avtomatik kuzatib boradi.\n"
            "O'z chat ID'ingizni bilish uchun: <code>/mening_id</code>"
        )
        return

    admin_section = (
        "<b>👤 Adminlar</b>\n"
        "/admin_qoshish &lt;id&gt; — yangi admin qo'shish\n"
        "/admin_ochirish &lt;id&gt; — adminlikdan chiqarish\n"
        "/adminlar — adminlar ro'yxati\n\n"
        if storage.is_founder(message.from_user.id)
        else ""
    )

    text = (
        "📋 <b>Barcha buyruqlar</b>\n\n"
        "<b>🤖 Bot holati</b>\n"
        "/botni_yoqish — botni yoqish\n"
        "/botni_ochirish — botni o'chirish (hech narsa tekshirilmaydi)\n"
        "/chatgpt_yoqish — AI tahlilini yoqish\n"
        "/chatgpt_ochirish — AI tahlilini o'chirish (arzonroq, kamroq aniq)\n"
        "/holat — joriy holatni ko'rish\n\n"
        f"{admin_section}"
        "<b>👥 Guruhlar</b>\n"
        "/hamma_guruh — barcha guruhlarni tinglash rejimi\n"
        "/tanlangan_guruhlar — faqat tanlangan guruhlarni tinglash rejimi\n"
        "/guruh_yoqish — shu guruhni (yoki <code>/guruh_yoqish -100...</code>) yoqish\n"
        "/guruh_ochirish — guruhni tinglashdan chiqarish\n"
        "/guruhlar — tinglanayotgan guruhlar ro'yxati\n\n"
        "<b>🚕 Shofyorlar</b>\n"
        "/shofyor_qoshish &lt;id&gt; — yangi shofyor qo'shish\n"
        "/shofyor_ochirish &lt;id&gt; — shofyorni o'chirish\n"
        "/shofyorlar — shofyorlar ro'yxati\n\n"
        "<b>ℹ️ Boshqa</b>\n"
        "/mening_id — o'z chat ID'ingizni bilish\n"
        "/menu — shu ro'yxatni qayta ko'rsatish"
    )
    await message.reply(text)
